<script>
    import { marked } from 'marked';
    import DOMPurify from 'dompurify';
    import { browser } from '$app/environment';
    import { onMount } from 'svelte';
    
    export let bannerMessage = null;
    
    let isExpanded = false;
    let isMobile = false;
    
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
    
    const typeStyles = {
        warning: 'bg-orange-50/95 dark:bg-orange-900/5 border-orange-200 dark:border-orange-800 text-orange-800 dark:text-orange-200',
        info: 'bg-blue-50/95 dark:bg-blue-900/5 border-blue-200 dark:border-blue-800 text-blue-800 dark:text-blue-200',
        success: 'bg-green-50/95 dark:bg-green-900/5 border-green-200 dark:border-green-800 text-green-800 dark:text-green-200'
    };
    

    const typeIcons = {
        warning: `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>`,
        
        info: `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clip-rule="evenodd"/>
        </svg>`,
        
        success: `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
        </svg>`,
        
        error: `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
        </svg>`
    };
    
    function renderMarkdown(content) {
        if (!content) return '';
        const rawHtml = marked.parse(content);
        return DOMPurify.sanitize(rawHtml);
    }
    

    function truncateText(text, maxLength = 100) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    // Plain Text aus HTML extrahieren für Vorschau
    function extractPlainText(html) {
        if (!html) return '';
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        return tempDiv.textContent || tempDiv.innerText || '';
    }
    
    $: htmlContent = bannerMessage ? renderMarkdown(bannerMessage.content) : '';
    $: previewText = htmlContent ? truncateText(extractPlainText(htmlContent), 60) : '';
    
    // Mobile Erkennung
    onMount(() => {
        if (browser) {
            const checkMobile = () => {
                isMobile = window.innerWidth < 768; // 768px als md-breakpoint
            };
            
            checkMobile();
            window.addEventListener('resize', checkMobile);
            
            return () => {
                window.removeEventListener('resize', checkMobile);
            };
        }
    });
    function closeBanner() {
        bannerMessage = null;
        isExpanded = false;
    }
</script>

{#if bannerMessage}
<div class="fixed {isMobile ? 'top-12' : 'top-4'} right-4 z-50 max-w-md w-[calc(100%-2rem)] md:w-auto">
    <div 
        class={`rounded-lg border shadow-lg ${typeStyles[bannerMessage.type] || typeStyles.warning} animate-slide-in`}
        role="alert"
        class:is-expanded={isExpanded}
    >
        <div class="p-4">
            <div class="flex items-start">
                <div class="flex-shrink-0 mr-3 text-lg py-2">
                    <!-- {typeIcons[bannerMessage.type] || '⚠️'} -->
                    {@html typeIcons[bannerMessage.type] || typeIcons.warning}
                </div>
                
                <div class="flex-1 min-w-0">
                    {#if isMobile && !isExpanded}
                        <!-- {/* Mobile: Nur Titel und Vorschau */} -->
                        <div class="flex items-center justify-between">
                            <div class="min-w-0">
                                <h3 class="font-semibold text-sm truncate">{bannerMessage.title}</h3>
                                {#if previewText}
                                    <p class="text-sm text-gray-600 dark:text-gray-400 truncate mt-1">
                                        {previewText}
                                    </p>
                                {/if}
                            </div>
                            <button 
                                class="ml-3 flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                                on:click={() => isExpanded = true}
                                aria-label="Mehr anzeigen"
                            >
                                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/>
                                </svg>
                            </button>
                        </div>
                    {:else}
                        <!-- {/* Desktop oder ausgeklapptes Mobile */} -->
                        <div>
                            <div class="flex items-start justify-between">
                                <h3 class="font-semibold text-md mb-1">{bannerMessage.title}</h3>
                                {#if isMobile}
                                    <button 
                                        class="ml-3 flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                                        on:click={() => isExpanded = false}
                                        aria-label="Weniger anzeigen"
                                    >
                                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                            <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd"/>
                                        </svg>
                                    </button>
                                {/if}
                            </div>
                            <div class="text-sm">
                                    {@html htmlContent}
                            </div>
                        </div>
                    {/if}
                </div>
                
                <!-- {/* Schließen-Button (außer bei mobile-collapsed state) */} -->
                {#if !isMobile || isExpanded}
                    <button 
                        class="ml-3 flex-shrink-0 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                        on:click={closeBanner}
                        aria-label="Schließen"
                    >
                        <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                        </svg>
                    </button>
                {/if}
            </div>
        </div>
    </div>
</div>

<style>
    @keyframes slide-in {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .animate-slide-in {
        animation: slide-in 0.3s ease-out;
    }
    
    /* Optional: Übergang für das Ausklappen */
    .is-expanded {
        transition: max-height 0.3s ease-out;
    }
</style>
{/if}