<script lang="ts">
    import { getContext, onMount } from "svelte";
    import UsersTab from "./UsersTab.svelte";
    import GroupsTabs from "./GroupsTabs.svelte";
    import { getUsers } from "$lib/apis/users";
    import { user } from '$lib/stores';


    let activeTab = 'users';
    const i18n = getContext('i18n');

    export let users = [];
    export let getUsersHandler: Function;
    export let getSubscription: Function;

    // $: if (activeTab) {
	// 	getUsersHandler();
	// }

	
   


</script>
<div class="flex flex-col pt-5">
    <div class="w-fit flex bg-lightGray-700 dark:bg-customGray-900 rounded-md mx-auto font-medium">
        <button
            on:click={() => (activeTab = 'users')}
            class="{activeTab === 'users' ? 'bg-lightGray-300 border-lightGray-400 dark:bg-customGray-900 rounded-md border dark:border-customGray-700 text-lightGray-100' : 'text-lightGray-100/70'} px-6 py-2 font-meduim flex-shrink-0 text-xs leading-none dark:text-customGray-100"
            >{$i18n.t('Users')}</button
        >
        <button
            on:click={() => (activeTab = 'groups')}
            class="{activeTab === 'groups' ? 'bg-lightGray-300 border-lightGray-400 dark:bg-customGray-900 rounded-md border dark:border-customGray-700 text-lightGray-100' : 'text-lightGray-100/70'} px-6 py-2 font-meduim flex-shrink-0 text-xs leading-none dark:text-customGray-100"
            >{$i18n.t('Groups')}</button
        >
    </div>
   
    <div>
        {#if activeTab === 'users'}
            <UsersTab {users} {getUsersHandler} {getSubscription}/>
         {:else if activeTab === 'groups'}
            <GroupsTabs {users}/>
        {/if}
    </div>
</div>