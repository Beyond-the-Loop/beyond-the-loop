<script lang="ts">
	import { v4 as uuidv4 } from 'uuid';
	import { toast } from 'svelte-sonner';
	import { Pane, PaneGroup } from 'paneforge';

	import { getContext, onDestroy, onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';

	import { type Unsubscriber, type Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { WEBUI_BASE_URL } from '$lib/constants';

	import { BufferedResponse } from '$lib/utils/buffer/BufferedResponse';

	import { getAlert } from '$lib/apis/alerts';

	import {
		chatId,
		chats,
		chatTitle,
		companyConfig,
		config,
		currentChatPage,
		mobile,
		type Model,
		models,
		modelsInfo,
		settings,
		showArtifacts,
		showCallOverlay,
		showChatInfoSidebar,
		showControls,
		showLibrary,
		showOverview,
		showSidebar,
		socket,
		tags as allTags,
		temporaryChatEnabled,
		user,
		WEBUI_NAME
	} from '$lib/stores';
	import {
		convertMessagesToHistory,
		copyToClipboard,
		createMessagesList,
		getMessageContentParts,
		promptTemplate,
		removeDetails
	} from '$lib/utils';

	import { createNewChat, getAllTags, getChatById, getChatList, getTagsById, updateChatById } from '$lib/apis/chats';
	import { generateMagicPrompt, generateOpenAIChatCompletion } from '$lib/apis/openai';
	import { processWeb, processYoutubeVideo } from '$lib/apis/retrieval';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import { queryMemory } from '$lib/apis/memories';
	import { getAndUpdateUserLocation, getUserSettings } from '$lib/apis/users';
	import { chatAction, chatCompleted, generateMoACompletion, stopTask } from '$lib/apis';
	import MessageInput from '$lib/components/chat/MessageInput.svelte';
	import ChatInfoSidebar from '$lib/components/chat/ChatInfoSidebar.svelte';
	import { analyzePII, type PIISpan } from '$lib/apis/pii';
	import Messages from '$lib/components/chat/Messages.svelte';
	import Navbar from '$lib/components/chat/Navbar.svelte';
	import AlertBanner from '$lib/components/chat/AlertBanner.svelte';
	import ChatControls from './ChatControls.svelte';
	import EventConfirmDialog from '../common/ConfirmDialog.svelte';
	import Placeholder from './Placeholder.svelte';
	import Spinner from '../common/Spinner.svelte';
	import ModelSelector from './ModelSelector.svelte';
	import BookIcon from '../icons/BookIcon.svelte';
	import DOMPurify from 'dompurify';
	import type { Alert } from '$lib/types';

	const i18n: Writable<i18nType> = getContext('i18n');

	export let chatIdProp = '';

	let loading = false;

	const eventTarget = new EventTarget();
	let controlPane;
	let controlPaneComponent;

	let autoScroll = true;
	let isAtTop = false;
	let processing = '';
	let messagesContainerElement: HTMLDivElement;

	let navbarElement;

	let taskId;

	let showEventConfirmation = false;
	let eventConfirmationTitle = '';
	let eventConfirmationMessage = '';
	let eventConfirmationInput = false;
	let eventConfirmationInputPlaceholder = '';
	let eventConfirmationInputValue = '';
	let eventCallback = null;

	let chatIdUnsubscriber: Unsubscriber | undefined;

	let selectedModels = [];
	let atSelectedModel: Model | undefined;
	let selectedModelIds = [];
	$: selectedModelIds = atSelectedModel !== undefined ? [atSelectedModel.id] : selectedModels;

	let imageGenerationEnabled = true;
	let webSearchEnabled = true;
	let codeInterpreterEnabled = true;
	let autoToolsEnabled = true;
	// Per-chat PII filter toggle. Lives here (not in MessageInput) so it
	// survives the composer's mount/unmount during send. Sent with every
	// chat-completion request as `pii_enabled`. Backend forces it back to
	// true if the user lacks `pii.allow_disable_in_chat`.
	let piiEnabled = true;
	let piiReleasedEntities: string[] = [];
	let showPiiDisableConfirm = false;
	$: hasAnonymizedMessages = Object.values(history?.messages ?? {}).some(
		(m: any) => m?.pii_status === 'full' || m?.pii_status === 'partial'
	);

	const handlePiiToggleClick = () => {
		if (piiEnabled && hasAnonymizedMessages) {
			showPiiDisableConfirm = true;
		} else {
			piiEnabled = !piiEnabled;
		}
	};

	// Live PII detection on the current prompt — feeds both the sidebar's
	// privacy section and the toggle button's count badge. Lives at this
	// level so detection state stays consistent across landing-page and
	// active-chat composer.
	let detectedPIIEntities: PIISpan[] = [];
	let piiAbortController: AbortController | null = null;
	let piiDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	const PII_DEBOUNCE_MS = 350;
	const PII_MIN_CHARS = 3;

	// Drives sidebar + privacy button visibility. The disable-toggle UI in
	// MessageInput is gated separately via `canRelaxPii`, so users without
	// the toggle permission still see the panel — they just can't turn it off
	// or release individual entities.
	$: piiPanelVisible =
		piiEnabled && ($companyConfig?.config?.privacy?.pii_filter_enabled ?? false);

	// Whether this user is allowed to disable the PII filter or release
	// individual entities. The backend enforces the same rule and silently
	// forces released[] back to empty otherwise, so the UI mirrors that.
	$: canRelaxPii =
		($companyConfig?.config?.privacy?.pii_filter_enabled ?? false) &&
		($user?.role === 'admin' || $user?.permissions?.pii?.allow_disable_in_chat);

	$: schedulePIIAnalyze(prompt, piiPanelVisible);

	function schedulePIIAnalyze(text: string, active: boolean) {
		if (piiDebounceTimer) clearTimeout(piiDebounceTimer);
		if (!active || !text || text.trim().length < PII_MIN_CHARS) {
			// Abort any in-flight analyze — otherwise its result lands AFTER the
			// reset and re-fills the sidebar with stale spans (e.g. right after
			// the user sends and prompt becomes empty).
			if (piiAbortController) piiAbortController.abort();
			detectedPIIEntities = [];
			return;
		}
		piiDebounceTimer = setTimeout(() => runPIIAnalyze(text), PII_DEBOUNCE_MS);
	}

	async function runPIIAnalyze(text: string) {
		if (piiAbortController) piiAbortController.abort();
		piiAbortController = new AbortController();
		try {
			const res = await analyzePII(localStorage.token, text, piiAbortController.signal);
			detectedPIIEntities = res.spans ?? [];
		} catch (err) {
			if ((err as any)?.name === 'AbortError') return;
			console.warn('[pii] analyze failed', err);
			detectedPIIEntities = [];
		}
	}

	$: uniquePIICount = (() => {
		const seen = new Set<string>();
		for (const span of detectedPIIEntities) seen.add(span.original);
		return seen.size;
	})();

	// Aggregate per-entity status across the whole chat. Entities can flip
	// between protected and released over time (user clicks the chip to
	// release in turn 2, doesn't release in turn 5 → re-anonymized). The
	// latest user message that mentions an entity wins.
	//
	// Sources are accumulated UNION across all messages — if a name first
	// shows up in the prompt and later in a file, both surfaces are surfaced
	// as separate cards in the sidebar (per user request).
	$: aggregatedChatPII = (() => {
		const userMessages = (Object.values(history?.messages ?? {}) as any[])
			.filter((m: any) => m?.role === 'user')
			.sort((a: any, b: any) => (a?.timestamp ?? 0) - (b?.timestamp ?? 0));

		const latestStatus: Record<string, 'protected' | 'released'> = {};
		const placeholderOf: Record<string, string> = {};
		const sourcesOf: Record<string, Set<string>> = {};

		for (const msg of userMessages) {
			const vars = msg.pii_variables;
			if (vars) {
				for (const [original, placeholder] of Object.entries(vars)) {
					placeholderOf[original] = placeholder as string;
					latestStatus[original] = 'protected';
				}
			}
			const sources = msg.pii_variable_sources;
			if (sources) {
				for (const [original, srcList] of Object.entries(sources)) {
					(sourcesOf[original] ??= new Set<string>());
					for (const s of srcList as string[]) sourcesOf[original].add(s);
				}
			}
			// released_actual is set after pii_variables for the same message,
			// so it overrides correctly within a single turn too.
			for (const original of msg.pii_released_entities_actual ?? []) {
				latestStatus[original] = 'released';
			}
		}

		const variables: Record<string, string> = {};
		const releasedList: string[] = [];
		const variableSources: Record<string, string[]> = {};
		for (const [original, status] of Object.entries(latestStatus)) {
			if (status === 'released') {
				releasedList.push(original);
			} else if (placeholderOf[original]) {
				variables[original] = placeholderOf[original];
				variableSources[original] = Array.from(sourcesOf[original] ?? []).sort();
			}
		}
		return {
			variables,
			variableSources,
			released: releasedList.sort((a, b) => a.localeCompare(b))
		};
	})();

	$: aggregatedChatPIIVariables = aggregatedChatPII.variables;
	$: aggregatedChatPIIVariableSources = aggregatedChatPII.variableSources;
	$: aggregatedChatReleasedEntities = aggregatedChatPII.released;

	onDestroy(() => {
		if (piiDebounceTimer) clearTimeout(piiDebounceTimer);
		if (piiAbortController) piiAbortController.abort();
	});
	let chat = null;
	let tags = [];
	let alert: Alert;

	let history = {
		messages: {},
		currentId: null
	};

	// Chat Input
	let prompt = '';
	let chatFiles = [];
	let files = [];
	let params = {};
	let isMagicLoading = false;
	let initNewChatCompleted = false;

	const getDefaultModels = (): string[] => {
		// In assistants-only mode, always return the first assistant
		if ($user?.permissions?.chat?.assistants_only) {
			const firstAssistant = $models.find((m) => m.base_model_id != null);
			if (firstAssistant) {
				return [firstAssistant.id];
			}
			return [];
		}

		const defaultModelIds = $companyConfig?.config?.models?.default_models?.split(',');
		const validDefaults = defaultModelIds?.filter((id) => $models.some((m) => m.id === id));

		if (validDefaults?.length > 0) {
			return validDefaults;
		}

		// Only consider base models (not assistants) when deciding whether to use Smart Router
		const baseModels = $models.filter((m) => m.base_model_id == null);
		const hasNonSmartRouterBase = baseModels.some((m) => m.name !== 'Smart Router');
		if (hasNonSmartRouterBase && baseModels.some((m) => m.name === 'Smart Router')) {
			return ['Smart Router'];
		}

		// Fall back to first assistant when no base models are available
		const firstAssistant = $models.find((m) => m.base_model_id != null);
		if (firstAssistant) {
			return [firstAssistant.id];
		}

		return [];
	};

	$: if (
		!chatIdProp &&
		$models.length > 0 &&
		(selectedModels.length === 0 || selectedModels.every((id) => !id || !$models.some((m) => m.id === id)))
	) {
		selectedModels = $page.url.searchParams.get('models') ? $page.url.searchParams.get('models').split(',') : getDefaultModels();
	}

	// When $user loads after $models (assistants-only): correct selection if a non-assistant is selected
	$: if (
		!chatIdProp &&
		$user?.permissions?.chat?.assistants_only &&
		$models.length > 0 &&
		!selectedModels.some((id) => $models.some((m) => m.id === id && m.base_model_id != null))
	) {
		const firstAssistant = $models.find((m) => m.base_model_id != null);
		if (firstAssistant) {
			selectedModels = [firstAssistant.id];
		}
	}

	$: if (chatIdProp) {
		(async () => {
			loading = true;

			prompt = '';
			files = [];
			webSearchEnabled = true;
			imageGenerationEnabled = false;

			if (chatIdProp && (await loadChat())) {
				await tick();
				loading = false;

				if (localStorage.getItem(`chat-input-${chatIdProp}`)) {
					try {
						const input = JSON.parse(localStorage.getItem(`chat-input-${chatIdProp}`));

						prompt = input.prompt;
						files = input.files;
						webSearchEnabled = input.webSearchEnabled;
						imageGenerationEnabled = input.imageGenerationEnabled;
						autoToolsEnabled = input.autoToolsEnabled ?? true;
					} catch (e) {
					}
				}

				window.setTimeout(() => scrollToBottom(), 0);
				const chatInput = document.getElementById('chat-input');
				chatInput?.focus();
			} else {
				await goto('/');
			}
		})();
	}

	

	const showMessage = async (message) => {
		const _chatId = JSON.parse(JSON.stringify($chatId));
		let _messageId = JSON.parse(JSON.stringify(message.id));

		let messageChildrenIds = history.messages[_messageId].childrenIds;

		while (messageChildrenIds.length !== 0) {
			_messageId = messageChildrenIds.at(-1);
			messageChildrenIds = history.messages[_messageId].childrenIds;
		}

		history.currentId = _messageId;

		await tick();
		await tick();
		await tick();

		const messageElement = document.getElementById(`message-${message.id}`);
		if (messageElement) {
			messageElement.scrollIntoView({ behavior: 'smooth' });
		}

		await tick();
		saveChatHandler(_chatId, history);
	};

	const chatEventHandler = async (event, cb) => {
		if (event.chat_id === $chatId) {
			await tick();
			let message = history.messages[event.message_id];

			if (message) {
				const type = event?.data?.type ?? null;
				const data = event?.data?.data ?? null;

				if (type === 'status') {
					if (message?.statusHistory) {
						message.statusHistory.push(data);
					} else {
						message.statusHistory = [data];
					}
				} else if (type === 'source' || type === 'citation') {
					if (data?.type === 'code_execution') {
						// Code execution; update existing code execution by ID, or add new one.
						if (!message?.code_executions) {
							message.code_executions = [];
						}

						const existingCodeExecutionIndex = message.code_executions.findIndex(
							(execution) => execution.id === data.id
						);

						if (existingCodeExecutionIndex !== -1) {
							message.code_executions[existingCodeExecutionIndex] = data;
						} else {
							message.code_executions.push(data);
						}

						message.code_executions = message.code_executions;
					} else {
						// Regular source.
						if (message?.sources) {
							message.sources.push(data);
						} else {
							message.sources = [data];
						}
					}
				} else if (type === 'chat:completion') {
					chatCompletionEventHandler(data, message, event.chat_id);
				} else if (type === 'chat:title') {
					chatTitle.set(data);
					currentChatPage.set(1);
					await chats.set(await getChatList(localStorage.token, $currentChatPage));
				} else if (type === 'chat:tags') {
					chat = await getChatById(localStorage.token, $chatId);
					allTags.set(await getAllTags(localStorage.token));
				} else if (type === 'message') {
					message.content += data.content;
				} else if (type === 'replace') {
					message.content = data.content;
				} else if (type === 'action') {
					if (data.action === 'continue') {
						const continueButton = document.getElementById('continue-response-button');

						if (continueButton) {
							continueButton.click();
						}
					}
				} else if (type === 'confirmation') {
					eventCallback = cb;

					eventConfirmationInput = false;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
				} else if (type === 'execute') {
					eventCallback = cb;

					try {
						// Use Function constructor to evaluate code in a safer way
						const asyncFunction = new Function(`return (async () => { ${data.code} })()`);
						const result = await asyncFunction(); // Await the result of the async function

						if (cb) {
							cb(result);
						}
					} catch (error) {
						console.error('Error executing code:', error);
					}
				} else if (type === 'input') {
					eventCallback = cb;

					eventConfirmationInput = true;
					showEventConfirmation = true;

					eventConfirmationTitle = data.title;
					eventConfirmationMessage = data.message;
					eventConfirmationInputPlaceholder = data.placeholder;
					eventConfirmationInputValue = data?.value ?? '';
				} else if (type === 'notification') {
					const toastType = data?.type ?? 'info';
					const toastContent = data?.content ?? '';

					if (toastType === 'success') {
						toast.success(toastContent);
					} else if (toastType === 'error') {
						toast.error(toastContent);
					} else if (toastType === 'warning') {
						toast.warning(toastContent);
					} else {
						toast.info(toastContent);
					}
				} else if (type === 'file_refs') {
					if (!message.fileRefs) {
						message.fileRefs = [];
					}
					message.fileRefs.push(...(data ?? []));
				} else if (type === 'pii:user_message') {
					// Backend echo after all PII passes (user message, files, RAG).
					// `filtered_content` drives the inline diff in the modal;
					// `variables` lists every original/placeholder pair the LLM saw;
					// `pii_status` is "full" | "partial" | "none" — drives the badge
					// on the user message in the chat history.
					//
					// This event arrives over Socket.IO while the response itself
					// streams via SSE — the two transports race. The streaming-done
					// save (chatCompletionEventHandler) may run before this event
					// lands, so we MUST save again here, otherwise the badge shows
					// in memory but vanishes on reload from DB.
					const userMessageId = message.parentId;
					if (userMessageId && history.messages[userMessageId]) {
						history.messages[userMessageId].filtered_content = data.filtered_content;
						history.messages[userMessageId].pii_variables = data.variables;
						history.messages[userMessageId].pii_variable_sources = data.variable_sources;
						history.messages[userMessageId].pii_released_entities_actual = data.released_entities;
						history.messages[userMessageId].pii_status = data.pii_status;
						saveChatHandler($chatId, history);
					}
				} else {
					console.log('Unknown message type', data);
				}

				history.messages[event.message_id] = message;

				if (autoScroll && type !== 'chat:completion') {
					scrollToBottom();
				}
			}
		}
	};

	const onMessageHandler = async (event: {
		origin: string;
		data: { type: string; text: string };
	}) => {
		if (event.origin !== window.origin) {
			return;
		}

		// Replace with your iframe's origin
		if (event.data.type === 'input:prompt') {
			console.debug(event.data.text);

			const inputElement = document.getElementById('chat-input');

			if (inputElement) {
				prompt = event.data.text;
				inputElement.focus();
			}
		}

		if (event.data.type === 'action:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitPrompt(prompt);
			}
		}

		if (event.data.type === 'input:prompt:submit') {
			console.debug(event.data.text);

			if (prompt !== '') {
				await tick();
				submitPrompt(event.data.text);
			}
		}
	};

	onMount(async () => {
		window.addEventListener('message', onMessageHandler);
		$socket?.on('chat-events', chatEventHandler);

		if (!$chatId) {
			chatIdUnsubscriber = chatId.subscribe(async (value) => {
				if (!value) {
					await initNewChat();
					initNewChatCompleted = true;
				}
			});
		} else {
			if ($temporaryChatEnabled) {
				await goto('/');
			}
		}

		if (localStorage.getItem(`chat-input-${chatIdProp}`)) {
			try {
				const input = JSON.parse(localStorage.getItem(`chat-input-${chatIdProp}`));
				prompt = input.prompt;
				files = input.files;
				webSearchEnabled = input.webSearchEnabled;
				imageGenerationEnabled = input.imageGenerationEnabled;
				autoToolsEnabled = input.autoToolsEnabled ?? true;
			} catch (e) {
				prompt = '';
				files = [];
				webSearchEnabled = true;
				imageGenerationEnabled = true;
				autoToolsEnabled = true;
			}
		}

		showControls.subscribe(async (value) => {
			if (controlPane && !$mobile) {
				try {
					if (value) {
						controlPaneComponent.openPane();
					} else {
						controlPane.collapse();
					}
				} catch (e) {
					// ignore
				}
			}

			if (!value) {
				showCallOverlay.set(false);
				showOverview.set(false);
				showArtifacts.set(false);
			}
		});

		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		chats.subscribe(() => {
		});

		alert = await getAlert();
	});

	onDestroy(() => {
		chatIdUnsubscriber?.();
		window.removeEventListener('message', onMessageHandler);
		$socket?.off('chat-events', chatEventHandler);
	});

	// File upload functions

	const uploadGoogleDriveFile = async (fileData) => {
		// Validate input
		if (!fileData?.id || !fileData?.name || !fileData?.url || !fileData?.headers?.Authorization) {
			throw new Error('Invalid file data provided');
		}

		const tempItemId = uuidv4();
		const fileItem = {
			type: 'file',
			file: '',
			id: null,
			url: fileData.url,
			name: fileData.name,
			collection_name: '',
			status: 'uploading',
			error: '',
			itemId: tempItemId,
			size: 0
		};

		try {
			files = [...files, fileItem];

			// Configure fetch options with proper headers
			const fetchOptions = {
				headers: {
					Authorization: fileData.headers.Authorization,
					Accept: '*/*'
				},
				method: 'GET'
			};

			// Attempt to fetch the file
			const fileResponse = await fetch(fileData.url, fetchOptions);

			if (!fileResponse.ok) {
				const errorText = await fileResponse.text();
				throw new Error(`Failed to fetch file (${fileResponse.status}): ${errorText}`);
			}

			// Get content type from response
			const contentType = fileResponse.headers.get('content-type') || 'application/octet-stream';

			// Convert response to blob
			const fileBlob = await fileResponse.blob();

			if (fileBlob.size === 0) {
				throw new Error('Retrieved file is empty');
			}

			// Create File object with proper MIME type
			const file = new File([fileBlob], fileData.name, {
				type: fileBlob.type || contentType
			});

			if (file.size === 0) {
				throw new Error('Created file is empty');
			}

			// Upload file to server
			const uploadedFile = await uploadFile(localStorage.token, file);

			if (!uploadedFile) {
				throw new Error('Server returned null response for file upload');
			}

			// Update file item with upload results
			fileItem.status = 'uploaded';
			fileItem.file = uploadedFile;
			fileItem.id = uploadedFile.id;
			fileItem.size = file.size;
			fileItem.collection_name = uploadedFile?.meta?.collection_name;
			fileItem.url = `${WEBUI_API_BASE_URL}/files/${uploadedFile.id}`;

			files = files;
			toast.success($i18n.t('File uploaded successfully'));
		} catch (e) {
			console.error('Error uploading file:', e);
			files = files.filter((f) => f.itemId !== tempItemId);
			toast.error(
				$i18n.t('Error uploading file: {{error}}', {
					error: e.message || 'Unknown error'
				})
			);
		}
	};

	const uploadWeb = async (url) => {
		const fileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processWeb(localStorage.token, '', url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};

				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(JSON.stringify(e));
		}
	};

	const uploadYoutubeTranscription = async (url) => {
		const fileItem = {
			type: 'doc',
			name: url,
			collection_name: '',
			status: 'uploading',
			context: 'full',
			url: url,
			error: ''
		};

		try {
			files = [...files, fileItem];
			const res = await processYoutubeVideo(localStorage.token, url);

			if (res) {
				fileItem.status = 'uploaded';
				fileItem.collection_name = res.collection_name;
				fileItem.file = {
					...res.file,
					...fileItem.file
				};
				files = files;
			}
		} catch (e) {
			// Remove the failed doc from the files array
			files = files.filter((f) => f.name !== url);
			toast.error(`${e}`);
		}
	};

	//////////////////////////
	// Web functions
	//////////////////////////

	const initNewChat = async () => {
		selectedModels = $page.url.searchParams.get('models') ? $page.url.searchParams.get('models').split(',') : getDefaultModels();

		await showControls.set(false);
		await showCallOverlay.set(false);
		await showOverview.set(false);
		await showArtifacts.set(false);

		if ($page.url.pathname.includes('/c/')) {
			window.history.replaceState(history.state, '', `/`);
		}

		autoScroll = true;

		await chatId.set('');
		await chatTitle.set('');

		history = {
			messages: {},
			currentId: null
		};

		chatFiles = [];
		params = {};
		piiReleasedEntities = [];

		webSearchEnabled = true;
		imageGenerationEnabled = true;
		codeInterpreterEnabled = true;
		autoToolsEnabled = true;

		if ($page.url.searchParams.get('youtube')) {
			uploadYoutubeTranscription(
				`https://www.youtube.com/watch?v=${$page.url.searchParams.get('youtube')}`
			);
		}
		if ($page.url.searchParams.get('web-search') === 'true') {
			webSearchEnabled = true;
		}

		if ($page.url.searchParams.get('image-generation') === 'true') {
			imageGenerationEnabled = true;
		}

		if ($page.url.searchParams.get('call') === 'true') {
			showCallOverlay.set(true);
			showControls.set(true);
		}

		if ($page.url.searchParams.get('q')) {
			prompt = $page.url.searchParams.get('q') ?? '';

			if (prompt) {
				await tick();
				submitPrompt(prompt);
			}
		}

		const userSettings = await getUserSettings(localStorage.token);

		if (userSettings) {
			settings.set(userSettings.ui);
		} else {
			settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
		}

		const chatInput = document.getElementById('chat-input');
		setTimeout(() => chatInput?.focus(), 0);
	};

	const loadChat = async () => {
		chatId.set(chatIdProp);
		chat = await getChatById(localStorage.token, $chatId).catch(async (error) => {
			await goto('/');
			return;
		});

		if (chat) {
			tags = await getTagsById(localStorage.token, $chatId).catch(async (error) => {
				return [];
			});

			const chatContent = chat.chat;

			if (chatContent) {
				selectedModels =
					(chatContent?.models ?? undefined) !== undefined
						? chatContent.models
						: [chatContent.models ?? ''];
				history =
					(chatContent?.history ?? undefined) !== undefined
						? chatContent.history
						: convertMessagesToHistory(chatContent.messages);

				chatTitle.set(chatContent.title);

				const userSettings = await getUserSettings(localStorage.token);

				if (userSettings) {
					await settings.set(userSettings.ui);
				} else {
					await settings.set(JSON.parse(localStorage.getItem('settings') ?? '{}'));
				}

				params = chatContent?.params ?? {};
				chatFiles = chatContent?.files ?? [];
				piiReleasedEntities = Array.isArray(chatContent?.pii_released_entities)
					? chatContent.pii_released_entities
					: [];

				autoScroll = true;
				await tick();

				return true;
			} else {
				return null;
			}
		}
	};

	const scrollToBottom = async () => {
		await tick();
		if (messagesContainerElement) {
			messagesContainerElement.scrollTop = messagesContainerElement.scrollHeight;
		}
	};
	const chatCompletedHandler = async (chatId, modelId, responseMessageId, messages) => {
		const res = await chatCompleted(localStorage.token, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };

			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				if (message?.id) {
					// Add null check for message and message.id
					history.messages[message.id] = {
						...history.messages[message.id],
						...(history.messages[message.id].content !== message.content
							? { originalContent: history.messages[message.id].content }
							: {}),
						...message
					};
				}
			}
		}

		await tick();

		if ($chatId == chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					params: params,
					files: chatFiles
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const chatActionHandler = async (chatId, actionId, modelId, responseMessageId, event = null) => {
		const messages = createMessagesList(history, responseMessageId);

		const res = await chatAction(localStorage.token, actionId, {
			model: modelId,
			messages: messages.map((m) => ({
				id: m.id,
				role: m.role,
				content: m.content,
				info: m.info ? m.info : undefined,
				timestamp: m.timestamp,
				...(m.sources ? { sources: m.sources } : {})
			})),
			...(event ? { event: event } : {}),
			chat_id: chatId,
			session_id: $socket?.id,
			id: responseMessageId
		}).catch((error) => {
			toast.error(`${error}`);
			messages.at(-1).error = { content: error };
			return null;
		});

		if (res !== null && res.messages) {
			// Update chat history with the new messages
			for (const message of res.messages) {
				history.messages[message.id] = {
					...history.messages[message.id],
					...(history.messages[message.id].content !== message.content
						? { originalContent: history.messages[message.id].content }
						: {}),
					...message
				};
			}
		}

		if ($chatId == chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, chatId, {
					models: selectedModels,
					messages: messages,
					history: history,
					params: params,
					files: chatFiles
				});

				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};

	const createMessagePair = async (userPrompt) => {
		prompt = '';
		if (selectedModels.length === 0) {
			toast.error($i18n.t('Model not selected'));
		} else {
			const modelId = selectedModels[0];
			const model = $models.filter((m) => m.id === modelId).at(0);

			const messages = createMessagesList(history, history.currentId);
			const parentMessage = messages.length !== 0 ? messages.at(-1) : null;

			const userMessageId = uuidv4();
			const responseMessageId = uuidv4();

			const userMessage = {
				id: userMessageId,
				parentId: parentMessage ? parentMessage.id : null,
				childrenIds: [responseMessageId],
				role: 'user',
				content: userPrompt ? userPrompt : `[PROMPT] ${userMessageId}`,
				timestamp: Math.floor(Date.now() / 1000)
			};

			const responseMessage = {
				id: responseMessageId,
				parentId: userMessageId,
				childrenIds: [],
				role: 'assistant',
				content: `[RESPONSE] ${responseMessageId}`,
				done: true,

				model: modelId,
				modelName: model.name ?? model.id,
				modelIdx: 0,
				timestamp: Math.floor(Date.now() / 1000)
			};

			if (parentMessage) {
				parentMessage.childrenIds.push(userMessageId);
				history.messages[parentMessage.id] = parentMessage;
			}
			history.messages[userMessageId] = userMessage;
			history.messages[responseMessageId] = responseMessage;

			history.currentId = responseMessageId;

			await tick();

			if (autoScroll) {
				scrollToBottom();
			}

			if (messages.length === 0) {
				await initChatHandler(history);
			} else {
				await saveChatHandler($chatId, history);
			}
		}
	};

	const addMessages = async ({ modelId, parentId, messages }) => {
		const model = $models.filter((m) => m.id === modelId).at(0);

		let parentMessage = history.messages[parentId];
		let currentParentId = parentMessage ? parentMessage.id : null;
		for (const message of messages) {
			let messageId = uuidv4();

			if (message.role === 'user') {
				const userMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = userMessage;
				parentMessage = userMessage;
				currentParentId = messageId;
			} else {
				const responseMessage = {
					id: messageId,
					parentId: currentParentId,
					childrenIds: [],
					done: true,
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: 0,
					timestamp: Math.floor(Date.now() / 1000),
					...message
				};

				if (parentMessage) {
					parentMessage.childrenIds.push(messageId);
					history.messages[parentMessage.id] = parentMessage;
				}

				history.messages[messageId] = responseMessage;
				parentMessage = responseMessage;
				currentParentId = messageId;
			}
		}

		history.currentId = currentParentId;
		await tick();

		if (autoScroll) {
			scrollToBottom();
		}

		if (messages.length === 0) {
			await initChatHandler(history);
		} else {
			await saveChatHandler($chatId, history);
		}
	};

	let bufferedResponse: BufferedResponse | null = null;

	const chatCompletionEventHandler = async (data, message, chatId) => {
		const {
			id,
			done,
			choices,
			content,
			added_content,
			type,
			sources,
			selected_model_id,
			selectedModelId,
			model: updatedModel,
			error,
			usage,
			files
		} = data;

		if (error) {
			await handleOpenAIError(error, message);
		}

		if (sources) {
			message.sources = sources;
			if(bufferedResponse){
				bufferedResponse.add_sources(sources);
			}
		}

		if (choices) {
			if (choices[0]?.message?.content) {
				// Non-stream response
				message.content += choices[0]?.message?.content;
			} else {
				// Stream response
				let value = choices[0]?.delta?.content ?? '';
				if (message.content == '' && value == '\n') {
					console.log('Empty response');
				} else {
					message.content += value;

					if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
						navigator.vibrate(5);
					}

					// Emit chat event for TTS
					const messageContentParts = getMessageContentParts(
						message.content,
						$config?.audio?.tts?.split_on ?? 'punctuation'
					);
					messageContentParts.pop();

					// dispatch only last sentence and make sure it hasn't been dispatched before
					if (
						messageContentParts.length > 0 &&
						messageContentParts[messageContentParts.length - 1] !== message.lastSentence
					) {
						message.lastSentence = messageContentParts[messageContentParts.length - 1];
						eventTarget.dispatchEvent(
							new CustomEvent('chat', {
								detail: {
									id: message.id,
									content: messageContentParts[messageContentParts.length - 1]
								}
							})
						);
					}
				}
			}
		}

		if (content) {
			if (type == 'text') {
				if (bufferedResponse != null && added_content != null && added_content != undefined) {
					bufferedResponse.add_content(added_content);
				} else if (bufferedResponse === null) {
					message.content = content;
					bufferedResponse = new BufferedResponse(message, history, {
						onCommit: (msg) => {
							// Trigger Svelte Reactivity Update
							history.messages = {
								...history.messages,
								[msg.id]: { ...msg }
							};
							if (autoScroll) scrollToBottom();
						}
					});
				}
			} else {
				message.content = content;
				bufferedResponse?.stop();
				bufferedResponse = null;
			}

			// REALTIME_CHAT_SAVE is disabled

			if (navigator.vibrate && ($settings?.hapticFeedback ?? false)) {
				navigator.vibrate(5);
			}

			// Emit chat event for TTS
			const messageContentParts = getMessageContentParts(
				message.content,
				$config?.audio?.tts?.split_on ?? 'punctuation'
			);
			messageContentParts.pop();

			// dispatch only last sentence and make sure it hasn't been dispatched before
			if (
				messageContentParts.length > 0 &&
				messageContentParts[messageContentParts.length - 1] !== message.lastSentence
			) {
				message.lastSentence = messageContentParts[messageContentParts.length - 1];
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: {
							id: message.id,
							content: messageContentParts[messageContentParts.length - 1]
						}
					})
				);
			}
		}

		if (selected_model_id) {
			message.selectedModelId = selected_model_id;
			message.arena = true;
		}

		if (selectedModelId) {
			message.selectedModelId = selectedModelId;
		}

		if (updatedModel && !choices) {
			message.model = updatedModel;
		}

		if (usage) {
			message.usage = usage;
		}

		history.messages[message.id] = message;

		if (done) {
			bufferedResponse?.stop();
			bufferedResponse = null;

			message.done = true;
			message.content = content;

			if (files && files.length > 0) {
				message.files = [...(message.files ?? []), ...files];
			}

			if ($settings.responseAutoCopy) {
				copyToClipboard(message.content);
			}

			if ($settings.responseAutoPlayback && !$showCallOverlay) {
				await tick();
				document.getElementById(`speak-button-${message.id}`)?.click();
			}

			// Emit chat event for TTS
			let lastMessageContentPart =
				getMessageContentParts(message.content, $config?.audio?.tts?.split_on ?? 'punctuation')?.at(
					-1
				) ?? '';
			if (lastMessageContentPart) {
				eventTarget.dispatchEvent(
					new CustomEvent('chat', {
						detail: { id: message.id, content: lastMessageContentPart }
					})
				);
			}
			eventTarget.dispatchEvent(
				new CustomEvent('chat:finish', {
					detail: {
						id: message.id,
						content: message.content
					}
				})
			);

			history.messages[message.id] = message;
			await chatCompletedHandler(
				chatId,
				message.model,
				message.id,
				createMessagesList(history, message.id)
			);
		}

		if (autoScroll) {
			scrollToBottom();
		}
	};

	//////////////////////////
	// Chat functions
	//////////////////////////

	const submitPrompt = async (userPrompt, { _raw = false } = {}) => {
		const messages = createMessagesList(history, history.currentId);
		const _selectedModels = selectedModels.map((modelId) =>
			$models.map((m) => m.id).includes(modelId) ? modelId : ''
		);
		if (JSON.stringify(selectedModels) !== JSON.stringify(_selectedModels)) {
			selectedModels = _selectedModels;
		}

		if (userPrompt === '') {
			toast.error($i18n.t('Please enter a prompt'));
			return;
		}
		if (selectedModels.includes('')) {
			toast.error($i18n.t('Model not selected'));
			return;
		}

		if (messages.length != 0 && messages.at(-1).done != true) {
			// Response not done
			return;
		}
		if (messages.length != 0 && messages.at(-1).error) {
			// Error in response
			toast.error($i18n.t(`Oops! There was an error in the previous response.`));
			return;
		}
		if (
			files.length > 0 &&
			files.filter((file) => file.type !== 'image' && file.status === 'uploading').length > 0
		) {
			toast.error(
				$i18n.t(`Oops! There are files still uploading. Please wait for the upload to complete.`)
			);
			return;
		}
		if (
			($config?.file?.max_count ?? null) !== null &&
			files.length + chatFiles.length > $config?.file?.max_count
		) {
			toast.error(
				$i18n.t(`You can only chat with a maximum of {{maxCount}} file(s) at a time.`, {
					maxCount: $config?.file?.max_count
				})
			);
			return;
		}

		prompt = '';

		// Reset chat input textarea
		const chatInputElement = document.getElementById('chat-input');

		if (chatInputElement) {
			chatInputElement.style.height = '';
		}

		const _files = JSON.parse(JSON.stringify(files));
		chatFiles.push(..._files.filter((item) => ['doc', 'file', 'collection'].includes(item.type)));
		chatFiles = chatFiles.filter(
			// Remove duplicates
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		files = [];
		prompt = '';

		// Create user message
		let userMessageId = uuidv4();
		let userMessage = {
			id: userMessageId,
			parentId: messages.length !== 0 ? messages.at(-1).id : null,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			files: _files.length > 0 ? _files : undefined,
			timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			models: selectedModels
		};

		// Add message to history and Set currentId to messageId
		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		// Append messageId to childrenIds of parent message
		if (messages.length !== 0) {
			history.messages[messages.at(-1).id].childrenIds.push(userMessageId);
		}

		// focus on chat input
		const chatInput = document.getElementById('chat-input');
		chatInput?.focus();

		await sendPrompt(history, userPrompt, userMessageId, { newChat: true });
	};

	const submitMagicPrompt = async (userPrompt) => {
		isMagicLoading = true;

		try {
			const res = await generateMagicPrompt(localStorage.token, { prompt: userPrompt });
			prompt = res;
			const chatInputContainerElement = document.getElementById('chat-input-container');
			const chatInputElement = document.getElementById('chat-input');

			await tick();
			if (chatInputContainerElement) {
				chatInputContainerElement.style.height = '';
				chatInputContainerElement.style.height =
					Math.min(chatInputContainerElement.scrollHeight, 200) + 'px';
			}

			await tick();
			if (chatInputElement) {
				chatInputElement.focus();
				chatInputElement.dispatchEvent(new Event('input'));
			}
		} catch (err) {
			console.error('Magic prompt error:', err);
		} finally {
			isMagicLoading = false;
		}
	};

	const sendPrompt = async (
		_history,
		prompt: string,
		parentId: string,
		{ modelId = null, modelIdx = null, newChat = false } = {}
	) => {
		let _chatId = JSON.parse(JSON.stringify($chatId));
		_history = JSON.parse(JSON.stringify(_history));

		const responseMessageIds: Record<PropertyKey, string> = {};
		// If modelId is provided, use it, else use selected model
		let selectedModelIds = modelId
			? [modelId]
			: atSelectedModel !== undefined
				? [atSelectedModel.id]
				: selectedModels;

		// Create response messages for each selected model
		for (const [_modelIdx, modelId] of selectedModelIds.entries()) {
			const model = $models.filter((m) => m.id === modelId).at(0);

			if (model) {
				let responseMessageId = uuidv4();
				let responseMessage = {
					parentId: parentId,
					id: responseMessageId,
					childrenIds: [],
					role: 'assistant',
					content: '',
					model: model.id,
					modelName: model.name ?? model.id,
					modelIdx: modelIdx ? modelIdx : _modelIdx,
					userContext: null,
					timestamp: Math.floor(Date.now() / 1000) // Unix epoch
				};

				// Add message to history and Set currentId to messageId
				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;

				// Append messageId to childrenIds of parent message
				if (parentId !== null && history.messages[parentId]) {
					// Add null check before accessing childrenIds
					history.messages[parentId].childrenIds = [
						...history.messages[parentId].childrenIds,
						responseMessageId
					];
				}

				responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`] = responseMessageId;
			}
		}
		history = history;

		// Create new chat if newChat is true and first user message
		if (newChat && _history.messages[_history.currentId].parentId === null) {
			_chatId = await initChatHandler(_history);
		}

		await tick();

		_history = JSON.parse(JSON.stringify(history));

		// Guard: user clicked "New Chat" while we were awaiting initChatHandler/tick
		// history was cleared by initNewChat(), so there's nothing to send
		if (!_history.currentId) {
			return;
		}

		// Save chat after all messages have been created
		await saveChatHandler(_chatId, _history);

		await Promise.all(
			selectedModelIds.map(async (modelId, _modelIdx) => {
				const model = $models.filter((m) => m.id === modelId).at(0);

				if (model) {
					const messages = createMessagesList(_history, parentId);
					// If there are image files, check if model is vision capable
					const hasImages = messages.some((message) =>
						message.files?.some((file) => file.type === 'image')
					);

					if (hasImages && $modelsInfo[model.name]?.supports_image_input === false) {
						toast.error(
							$i18n.t('Model {{modelName}} is not vision capable', {
								modelName: model.name ?? model.id
							})
						);
					}

					let responseMessageId =
						responseMessageIds[`${modelId}-${modelIdx ? modelIdx : _modelIdx}`];
					let responseMessage = _history.messages[responseMessageId];

					let userContext = null;
					if ($settings?.memory ?? false) {
						if (userContext === null) {
							const res = await queryMemory(
								localStorage.token,
								prompt,
								_chatId,
								responseMessageId,
								$socket?.id
							).catch((error) => {
								toast.error(`${error}`);
								return null;
							});
							if (res) {
								if (res.documents[0].length > 0) {
									userContext = res.documents[0].reduce((acc, doc, index) => {
										const createdAtTimestamp = res.metadatas[0][index].created_at;
										const createdAtDate = new Date(createdAtTimestamp * 1000)
											.toISOString()
											.split('T')[0];
										return `${acc}${index + 1}. [${createdAtDate}]. ${doc}\n`;
									}, '');
								}
							}
						}
					}
					responseMessage.userContext = userContext;

					scrollToBottom();
					await sendPromptSocket(_history, model, responseMessageId, _chatId);
				} else {
					toast.error($i18n.t(`Model {{modelId}} not found`, { modelId }));
				}
			})
		);

		currentChatPage.set(1);
		chats.set(await getChatList(localStorage.token, $currentChatPage));
	};

	const sendPromptSocket = async (_history, model, responseMessageId, _chatId) => {
		const responseMessage = _history.messages[responseMessageId];
		const userMessage = _history.messages[responseMessage.parentId];

		let files = JSON.parse(JSON.stringify(chatFiles));
		files.push(
			...(userMessage?.files ?? []).filter((item) =>
				['doc', 'file', 'collection'].includes(item.type)
			),
			...(responseMessage?.files ?? []).filter((item) => ['web_search_results'].includes(item.type))
		);
		// Remove duplicates
		files = files.filter(
			(item, index, array) =>
				array.findIndex((i) => JSON.stringify(i) === JSON.stringify(item)) === index
		);

		scrollToBottom();
		eventTarget.dispatchEvent(
			new CustomEvent('chat:start', {
				detail: {
					id: responseMessageId
				}
			})
		);
		await tick();

		const stream =
			model?.info?.params?.stream_response ??
			$settings?.params?.stream_response ??
			params?.stream_response ??
			true;

		const historyMessages = createMessagesList(_history, responseMessageId).map((message) => ({
			...message,
			content: removeDetails(message.content, ['reasoning', 'code_interpreter'])
		}));

		const lastAssistantWithImages = [...historyMessages]
			.reverse()
			.find((m) => m.role === 'assistant' && m.files?.some((f) => f.type === 'image'));

		const messages = [
			!model.base_model_id && (params?.system || $settings.system || (responseMessage?.userContext ?? null))
				? {
					role: 'system',
					content: `${promptTemplate(
						params?.system ?? $settings?.system ?? '',
						`${$user.first_name} ${$user.last_name}`,
						$settings?.userLocation
							? await getAndUpdateUserLocation(localStorage.token)
							: undefined, model.name
					)}${
						(responseMessage?.userContext ?? null)
							? `\n\nUser Context:\n${responseMessage?.userContext ?? ''}`
							: ''
					}`
				}
				: undefined,
			...historyMessages
		]
			.filter((message) => message?.content?.trim())
			.map((message, idx, arr) => {
				const ownImages =
					(message.role === 'user' || message === lastAssistantWithImages)
						? (message.files?.filter((f) => f.type === 'image') ?? [])
						: [];

				// For user messages: also include generated images from the immediately preceding assistant turn
				const prevMsg = arr[idx - 1];
				const precedingGeneratedImages =
					message.role === 'user' && prevMsg?.role === 'assistant' && prevMsg?.files?.some((f) => f.type === 'image')
						? prevMsg.files.filter((f) => f.type === 'image')
						: [];

				const imageFiles = [...ownImages, ...precedingGeneratedImages];

				return {
					role: message.role,
					...(imageFiles.length > 0
						? {
							content: [
								{
									type: 'text',
									text: message?.merged?.content ?? message.content
								},
								...imageFiles.map((file) => ({
									type: 'image_url',
									image_url: {
										url: file.url
									}
								}))
							]
						}
						: {
							content: message?.merged?.content ?? message.content
						})
				};
			});

		const res = await generateOpenAIChatCompletion(
			localStorage.token,
			{
				stream: stream,
				model: model.id,
				messages: messages,
				params: {
					...$settings?.params,
					...params,

					format: $settings.requestFormat ?? undefined,
					keep_alive: $settings.keepAlive ?? undefined,
					stop:
						(params?.stop ?? $settings?.params?.stop ?? undefined)
							? (params?.stop.split(',').map((token) => token.trim()) ?? $settings.params.stop).map(
								(str) => decodeURIComponent(JSON.parse('"' + str.replace(/\"/g, '\\"') + '"'))
							)
							: undefined
				},

				files: (files?.length ?? 0) > 0 ? files : undefined,

				features: autoToolsEnabled
					? {}
					: {
						image_generation: imageGenerationEnabled,
						code_interpreter:
							$user.role === 'admin' || $user?.permissions?.features?.code_interpreter
								? codeInterpreterEnabled
								: false,
						web_search:
							$config?.features?.enable_web_search &&
							($user.role === 'admin' || $user?.permissions?.features?.web_search)
								? webSearchEnabled || ($settings?.webSearch ?? false) === 'always'
								: false
					},

				auto_tools: autoToolsEnabled
					? (() => {
							const _baseModel = model.base_model_id
								? $models.find((m) => m.id === model.base_model_id)
								: undefined;
							const _meta = _baseModel
								? $modelsInfo[_baseModel?.name]
								: $modelsInfo[model?.name];
							return [
								...($companyConfig?.config?.rag?.web?.search?.enable &&
								($user.role === 'admin' || $user?.permissions?.features?.web_search) &&
								(_meta?.supports_web_search ?? false)
									? ['web_search']
									: []),
								...((_meta?.supports_image_generation ?? false)
									? ['image_generation']
									: []),
								...(($user.role === 'admin' || $user?.permissions?.features?.code_interpreter) &&
								(_meta?.supports_code_execution ?? false)
									? ['code_interpreter']
									: [])
							];
						})()
					: undefined,

				session_id: $socket?.id,
				chat_id: _chatId,
				id: responseMessageId,

				pii_enabled: piiEnabled,
				pii_released_entities: piiReleasedEntities,

				...(!$temporaryChatEnabled &&
				(messages.length == 1 ||
					(messages.length == 2 &&
						messages.at(0)?.role === 'system' &&
						messages.at(1)?.role === 'user')) &&
				selectedModels[0] === model.id
					? {
						background_tasks: {
							title_generation: $settings?.title?.auto ?? true,
							tags_generation: $settings?.autoTags ?? true
						}
					}
					: {}),

			},
			`${WEBUI_BASE_URL}/api`)
			.catch((error) => {
				if (!error?.includes('402')) {
					if (error?.includes('ContentPolicyViolationError')) {
						toast.error(
							'The response was filtered due to the prompt triggering Azure OpenAI\'s content management policy. Please modify your prompt and retry.'
						);
					} else {
						toast.error(`${error}`);
					}
				}

				responseMessage.error = {
					content: error
				};
				responseMessage.done = true;

				history.messages[responseMessageId] = responseMessage;
				history.currentId = responseMessageId;
				return null;
			});

		if (res) {
			taskId = res.task_id;

			const responseMessage = history.messages[history.currentId];

			if (responseMessage) {

				// If responseMessage is already done it means that itx was stopped
				if (responseMessage.done) {
					stopTask(localStorage.token, taskId).catch((error) => {
						console.error('Failed to stop task:', error);
					});
				}
			}

			if (autoScroll) {
				await tick();
				scrollToBottom();
			}
		} else {
			await tick();
			scrollToBottom();
		}
	};

	const handleOpenAIError = async (error, responseMessage) => {
		let errorMessage = '';
		let innerError;

		if (error) {
			innerError = error;
		}

		console.error(innerError);
		if ('detail' in innerError) {
			toast.error(innerError.detail);
			errorMessage = innerError.detail;
		} else if ('error' in innerError) {
			if ('message' in innerError.error) {
				toast.error(innerError.error.message);
				errorMessage = innerError.error.message;
			} else {
				toast.error(innerError.error);
				errorMessage = innerError.error;
			}
		} else if ('message' in innerError) {
			toast.error(innerError.message);
			errorMessage = innerError.message;
		}

		responseMessage.error = {
			content: $i18n.t(`Uh-oh! There was an issue with the response.`) + '\n' + errorMessage
		};

		responseMessage.done = true;

		if (responseMessage.statusHistory) {
			responseMessage.statusHistory = responseMessage.statusHistory.filter(
				(status) => status.action !== 'knowledge_search'
			);
		}

		history.messages[responseMessage.id] = responseMessage;
	};

	const stopResponse = async () => {
		const _chatId = JSON.parse(JSON.stringify($chatId));
		const responseMessage = history.messages[history.currentId];

		if (responseMessage && !responseMessage.done) {
			if (taskId) {
				await stopTask(localStorage.token, taskId).catch((error) => {
					console.error('Failed to stop task:', error);
				});

				responseMessage.content = responseMessage.content.replaceAll(
					'<details type="reasoning" done="false">',
					'<details type="reasoning" done="true">'
				);

				if (bufferedResponse) {
					bufferedResponse.stop();
					bufferedResponse = null;
				}
			}

			responseMessage.done = true;
			history.messages[history.currentId] = responseMessage;
			await saveChatHandler(_chatId, history);
		}
	};

	const submitMessage = async (parentId, prompt) => {
		let userPrompt = prompt;
		let userMessageId = uuidv4();

		let userMessage = {
			id: userMessageId,
			parentId: parentId,
			childrenIds: [],
			role: 'user',
			content: userPrompt,
			models: selectedModels
		};

		if (parentId !== null) {
			history.messages[parentId].childrenIds = [
				...history.messages[parentId].childrenIds,
				userMessageId
			];
		}

		history.messages[userMessageId] = userMessage;
		history.currentId = userMessageId;

		await tick();
		await sendPrompt(history, userPrompt, userMessageId);
	};

	const regenerateResponse = async (message) => {
		if (history.currentId) {
			let userMessage = history.messages[message.parentId];
			let userPrompt = userMessage.content;

			if ((userMessage?.models ?? [...selectedModels]).length == 1) {
				// If user message has only one model selected, sendPrompt automatically selects it for regeneration
				await sendPrompt(history, userPrompt, userMessage.id);
			} else {
				// If there are multiple models selected, use the model of the response message for regeneration
				// e.g. many model chat
				await sendPrompt(history, userPrompt, userMessage.id, {
					modelId: message.model,
					modelIdx: message.modelIdx
				});
			}
		}
	};

	const continueResponse = async () => {
		const _chatId = JSON.parse(JSON.stringify($chatId));

		if (history.currentId && history.messages[history.currentId].done == true) {
			const responseMessage = history.messages[history.currentId];
			responseMessage.done = false;
			await tick();

			const model = $models
				.filter((m) => m.id === (responseMessage?.selectedModelId ?? responseMessage.model))
				.at(0);

			if (model) {
				await sendPromptSocket(history, model, responseMessage.id, _chatId);
			}
		}
	};

	const mergeResponses = async (messageId, responses, _chatId) => {
		const message = history.messages[messageId];
		const mergedResponse = {
			status: true,
			content: ''
		};
		message.merged = mergedResponse;
		history.messages[messageId] = message;

		try {
			const [res, controller] = await generateMoACompletion(
				localStorage.token,
				message.model,
				history.messages[message.parentId].content,
				responses
			);

			if (res && res.ok && res.body) {
				const textStream = await createOpenAITextStream(res.body, $settings.splitLargeChunks);
				for await (const update of textStream) {
					const { value, done, sources, error, usage } = update;
					if (error || done) {
						break;
					}

					if (mergedResponse.content == '' && value == '\n') {
						continue;
					} else {
						mergedResponse.content += value;
						history.messages[messageId] = message;
					}

					if (autoScroll) {
						scrollToBottom();
					}
				}

				await saveChatHandler(_chatId, history);
			} else {
				console.error(res);
			}
		} catch (e) {
			console.error(e);
		}
	};

	const initChatHandler = async (history) => {
		let _chatId = $chatId;

		if (!$temporaryChatEnabled) {
			chat = await createNewChat(localStorage.token, {
				id: _chatId,
				title: $i18n.t('New chat'),
				models: selectedModels,
				system: $settings.system ?? undefined,
				params: params,
				history: history,
				messages: createMessagesList(history, history.currentId),
				tags: [],
				timestamp: Date.now()
			});

			_chatId = chat.id;
			await chatId.set(_chatId);

			await chats.set(await getChatList(localStorage.token, $currentChatPage));
			currentChatPage.set(1);

			window.history.replaceState(history.state, '', `/c/${_chatId}`);
		} else {
			_chatId = 'local';
			await chatId.set('local');
		}
		await tick();

		return _chatId;
	};

	const saveChatHandler = async (_chatId, history) => {
		if ($chatId == _chatId) {
			if (!$temporaryChatEnabled) {
				chat = await updateChatById(localStorage.token, _chatId, {
					models: selectedModels,
					history: history,
					messages: createMessagesList(history, history.currentId),
					params: params,
					files: chatFiles,
					pii_released_entities: piiReleasedEntities
				});
				currentChatPage.set(1);
				await chats.set(await getChatList(localStorage.token, $currentChatPage));
			}
		}
	};
</script>

<svelte:head>
	<title>
		{$chatTitle
			? `${$chatTitle.length > 30 ? `${$chatTitle.slice(0, 30)}...` : $chatTitle} | ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

<audio id="audioElement" src="" style="display: none;" />

<EventConfirmDialog
	bind:show={showPiiDisableConfirm}
	title={$i18n.t('Disable PII filter?')}
	message={$i18n.t(
		'If you disable the PII filter for this chat, all further messages will be sent unredacted to the language model. Already redacted messages in this chat remain unchanged, but the rest of the conversation will continue in plain text.'
	)}
	confirmLabel={$i18n.t('Disable filter')}
	cancelLabel={$i18n.t('Cancel')}
	onConfirm={() => {
		piiEnabled = false;
	}}
/>

<EventConfirmDialog
	bind:show={showEventConfirmation}
	title={eventConfirmationTitle}
	message={eventConfirmationMessage}
	input={eventConfirmationInput}
	inputPlaceholder={eventConfirmationInputPlaceholder}
	inputValue={eventConfirmationInputValue}
	on:confirm={(e) => {
		if (e.detail) {
			eventCallback(e.detail);
		} else {
			eventCallback(true);
		}
	}}
	on:cancel={() => {
		eventCallback(false);
	}}
/>

<div
	class="h-screen max-h-[100dvh] transition-width duration-200 ease-in-out {$showSidebar
		? '  md:max-w-[calc(100%-260px)]'
		: ' '} w-full max-w-full flex flex-col"
	id="chat-container"
>
	{#if chatIdProp === '' || (!loading && chatIdProp)}
		{#if $settings?.backgroundImageUrl ?? null}
			<div
				class="absolute {$showSidebar
					? 'md:max-w-[calc(100%-260px)] md:translate-x-[260px]'
					: ''} top-0 left-0 w-full h-full bg-cover bg-center bg-no-repeat"
				style="background-image: url({$settings.backgroundImageUrl})  "
			/>

			<div
				class="absolute top-0 left-0 w-full h-full bg-gradient-to-t from-white to-white/85 dark:from-gray-900 dark:to-[#171717]/90 z-0"
			/>
		{/if}

		<Navbar
			bind:this={navbarElement}
			chat={{
				id: $chatId,
				chat: {
					title: $chatTitle,
					models: selectedModels,
					system: $settings.system ?? undefined,
					params: params,
					history: history,
					timestamp: Date.now()
				}
			}}
			title={$chatTitle}
			bind:selectedModels
			shareEnabled={!!history.currentId}
			{initNewChat}
		/>
		<PaneGroup direction="horizontal" class="w-full h-full">
			<Pane defaultSize={50} class="h-full flex w-full relative">
				{#if alert != null}
					<AlertBanner {alert} />
				{/if}

				<div class="flex flex-col flex-auto z-10 w-full @container">
					{#if $settings?.landingPageMode === 'chat' || createMessagesList(history, history.currentId).length > 0}
						<div
							class=" pb-2.5 flex flex-col justify-between w-full flex-auto overflow-auto h-0 max-w-full z-10 scrollbar-hidden"
							id="messages-container"
							bind:this={messagesContainerElement}
							on:scroll={(e) => {
								autoScroll =
									messagesContainerElement.scrollHeight - messagesContainerElement.scrollTop <=
									messagesContainerElement.clientHeight + 5;
								isAtTop = messagesContainerElement.scrollTop <= 5;
							}}
						>
							<div class=" h-full w-full flex flex-col">
								<Messages
									chatId={$chatId}
									bind:history
									bind:autoScroll
									bind:prompt
									{selectedModels}
									{sendPrompt}
									{showMessage}
									{submitMessage}
									{continueResponse}
									{regenerateResponse}
									{mergeResponses}
									{chatActionHandler}
									{addMessages}
									bottomPadding={files.length > 0}
								/>
							</div>
						</div>

						<div class=" pb-[1rem] max-w-[980px] mx-auto w-full">
							<div class="px-3 mb-2.5 flex items-center justify-between">
								<ModelSelector
									bind:selectedModels
								/>
								<div class="flex items-center gap-2">
									{#if piiPanelVisible}
										<button
											type="button"
											class="relative flex space-x-[5px] items-center py-[3px] px-[6px] rounded-md bg-lightGray-800 dark:bg-customGray-800 min-w-fit text-xs text-lightGray-100 dark:text-customGray-100 font-medium"
											aria-label={$i18n.t('Privacy panel')}
											on:click={() => showChatInfoSidebar.set(!$showChatInfoSidebar)}
										>
											<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" class="size-3.5">
												<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75 11.25 15 15 9.75m-3-7.036A11.959 11.959 0 0 1 3.598 6 11.99 11.99 0 0 0 3 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285Z" />
											</svg>
											<span>{$i18n.t('Privacy')}</span>
											{#if uniquePIICount > 0}
												<span
													class="ml-1 inline-flex items-center justify-center rounded-full bg-amber-500 text-white text-[10px] leading-none font-semibold min-w-[16px] h-[16px] px-1"
												>
													{uniquePIICount}
												</span>
											{/if}
										</button>
									{/if}
									<button
										class="flex space-x-[5px] items-center py-[3px] px-[6px] rounded-md bg-lightGray-800 dark:bg-customGray-800 min-w-fit text-xs text-lightGray-100 dark:text-customGray-100 font-medium"
										on:click={() => showLibrary.set(!$showLibrary)}
									>
										<BookIcon />
										<span>{$i18n.t('Library')}</span>
									</button>
								</div>
							</div>
							<div class="mb-4">
								<MessageInput
									{history}
									{selectedModels}
									bind:files
									bind:prompt
									bind:autoScroll
									bind:isAtTop
									bind:imageGenerationEnabled
									bind:codeInterpreterEnabled
									bind:webSearchEnabled
									bind:autoToolsEnabled
									bind:atSelectedModel
									{piiEnabled}
									showPiiToggle={canRelaxPii}
									onPiiToggle={handlePiiToggleClick}
									{isMagicLoading}
									transparentBackground={$settings?.backgroundImageUrl ?? false}
									{stopResponse}
									{createMessagePair}
									onChange={(input) => {
										if (input.prompt) {
											// files can exceed 5MB, which can break the local storage.
											if (input.files && input.files.length > 0) {
												input.files = [];
											}

											localStorage.setItem(`chat-input-${$chatId}`, JSON.stringify(input));
										} else {
											localStorage.removeItem(`chat-input-${$chatId}`);
										}
									}}
									on:upload={async (e) => {
										const { type, data } = e.detail;

										if (type === 'web') {
											await uploadWeb(data);
										} else if (type === 'youtube') {
											await uploadYoutubeTranscription(data);
										} else if (type === 'google-drive') {
											await uploadGoogleDriveFile(data);
										}
									}}
									on:submit={async (e) => {
										if (e.detail) {
											await tick();
											submitPrompt(
												($settings?.richTextInput ?? true)
													? e.detail.replaceAll('\n\n', '\n')
													: e.detail
											);
										}
									}}
									on:magicPrompt={async (e) => {
										if (e.detail) {
											await tick();
											submitMagicPrompt(
												($settings?.richTextInput ?? true)
													? e.detail.replaceAll('\n\n', '\n')
													: e.detail
											);
										}
									}}
								/>
							</div>

							<div
								class="user-notice absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
							>
								{#if $companyConfig?.config?.ui?.custom_user_notice}
									{@html DOMPurify.sanitize(
										$i18n.t($companyConfig?.config?.ui?.custom_user_notice),
										{ ADD_ATTR: ['target'] }
									)}
								{:else}
									{$i18n.t('LLMs can make mistakes. Verify important information.')}
								{/if}
							</div>
						</div>
					{:else}
						<div class="overflow-auto w-full h-full flex items-center">
							<Placeholder
								{history}
								{initNewChatCompleted}
								bind:selectedModels
								bind:files
								bind:prompt
								bind:autoScroll
								bind:imageGenerationEnabled
								bind:codeInterpreterEnabled
								bind:webSearchEnabled
								bind:autoToolsEnabled
								bind:atSelectedModel
								{piiEnabled}
								showPiiToggle={canRelaxPii}
								onPiiToggle={handlePiiToggleClick}
								showPiiPanel={piiPanelVisible}
								piiCount={uniquePIICount}
								{isMagicLoading}
								transparentBackground={$settings?.backgroundImageUrl ?? false}
								{stopResponse}
								{createMessagePair}
								on:upload={async (e) => {
									const { type, data } = e.detail;

									if (type === 'web') {
										await uploadWeb(data);
									} else if (type === 'youtube') {
										await uploadYoutubeTranscription(data);
									}
								}}
								on:submit={async (e) => {
									if (e.detail) {
										await tick();
										submitPrompt(
											($settings?.richTextInput ?? true)
												? e.detail.replaceAll('\n\n', '\n')
												: e.detail
										);
									}
								}}
								on:magicPrompt={async (e) => {
									if (e.detail) {
										await tick();
										submitMagicPrompt(
											($settings?.richTextInput ?? true)
												? e.detail.replaceAll('\n\n', '\n')
												: e.detail
										);
									}
								}}
							/>
							<div
								class="user-notice absolute bottom-1 text-xs text-gray-500 text-center line-clamp-1 right-0 left-0"
							>
								{#if $companyConfig?.config?.ui?.custom_user_notice}
									{@html DOMPurify.sanitize(
										$i18n.t($companyConfig?.config?.ui?.custom_user_notice),
										{ ADD_ATTR: ['target'] }
									)}
								{:else}
									{$i18n.t('LLMs can make mistakes. Verify important information.')}
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</Pane>

			<ChatControls
				bind:this={controlPaneComponent}
				bind:history
				bind:chatFiles
				bind:params
				bind:files
				bind:pane={controlPane}
				chatId={$chatId}
				modelId={selectedModelIds?.at(0) ?? null}
				models={selectedModelIds.reduce((a, e, i, arr) => {
					const model = $models.find((m) => m.id === e);
					if (model) {
						return [...a, model];
					}
					return a;
				}, [])}
				{submitPrompt}
				{stopResponse}
				{showMessage}
				{eventTarget}
			/>
		</PaneGroup>
	{:else if loading}
		<div class=" flex items-center justify-center h-full w-full">
			<div class="m-auto">
				<Spinner />
			</div>
		</div>
	{/if}
</div>

<ChatInfoSidebar
	privacyVisible={piiPanelVisible && (prompt?.trim().length ?? 0) > 0}
	detectedEntities={detectedPIIEntities}
	releasedEntities={piiReleasedEntities}
	onReleasedChange={(released) => (piiReleasedEntities = released)}
	privacyReleasable={canRelaxPii}
	historyVisible={true}
	historyVariables={aggregatedChatPIIVariables}
	historyVariableSources={aggregatedChatPIIVariableSources}
	historyReleased={aggregatedChatReleasedEntities}
/>
