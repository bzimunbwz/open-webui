<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME, config, mobile, showSidebar, user } from '$lib/stores';
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	$: navItems = [
		{ href: '/admin', label: 'Users', path: '/admin' },
		...($config?.features.enable_admin_analytics ?? true ? [{ href: '/admin/analytics', label: 'Analytics', path: '/admin/analytics' }] : []),
		{ href: '/admin/evaluations', label: 'Evaluations', path: '/admin/evaluations' },
		{ href: '/admin/functions', label: 'Functions', path: '/admin/functions' },
		{ href: '/admin/providers', label: 'Providers', path: '/admin/providers' },
		{ href: '/admin/packages', label: 'Packages', path: '/admin/packages' },
		{ href: '/admin/coupons', label: 'Coupons', path: '/admin/coupons' },
		{ href: '/admin/payments', label: 'Payments', path: '/admin/payments' },
		{ href: '/admin/settings', label: 'Settings', path: '/admin/settings' },
	];

	const isActive = (path: string) => {
		if (path === '/admin') {
			return $page.url.pathname === '/admin' || $page.url.pathname.startsWith('/admin/users');
		}
		return $page.url.pathname.startsWith(path);
	};

	onMount(async () => {
		if ($user?.role !== 'admin') {
			await goto('/');
		}
		loaded = true;
	});
</script>

<svelte:head>
	<title>
		{$i18n.t('Admin Panel')} • {$WEBUI_NAME}
	</title>
</svelte:head>

{#if loaded}
	<div
		class="admin-panel flex flex-col h-screen max-h-[100dvh] flex-1 transition-width duration-200 ease-in-out {$showSidebar
			? 'md:max-w-[calc(100%-var(--sidebar-width))]'
			: ' md:max-w-[calc(100%-49px)]'}  w-full max-w-full"
	>
		<nav class="admin-nav px-3 pt-2 backdrop-blur-xl drag-region select-none border-b border-white/[0.06]">
			<div class="flex items-center gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
						<Tooltip
							content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')}
							interactive={true}
						>
							<button
								id="sidebar-toggle-button"
								class="cursor-pointer flex rounded-lg hover:bg-white/[0.06] transition"
								on:click={() => {
									showSidebar.set(!$showSidebar);
								}}
							>
								<div class="self-center p-1.5">
									<Sidebar />
								</div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div class="flex w-full">
					<div
						class="flex gap-0.5 scrollbar-none overflow-x-auto w-fit text-center text-sm font-medium bg-transparent pb-0"
					>
						{#each navItems as item}
							<a
								draggable="false"
								class="admin-nav-tab min-w-fit px-3 py-2 rounded-t-lg transition-all duration-150 select-none relative
									{isActive(item.path)
										? 'text-white font-semibold admin-nav-tab-active'
										: 'text-gray-400 dark:text-gray-500 hover:text-gray-200 dark:hover:text-gray-300 hover:bg-white/[0.04]'}"
								href={item.href}
							>{$i18n.t(item.label)}</a>
						{/each}
					</div>
				</div>
			</div>
		</nav>

		<div class="pb-1 flex-1 max-h-full overflow-y-auto">
			<slot />
		</div>
	</div>
{/if}

<style>
	.admin-nav-tab-active::after {
		content: '';
		position: absolute;
		bottom: 0;
		left: 8px;
		right: 8px;
		height: 2px;
		background: linear-gradient(90deg, #d4a574, #c4956a);
		border-radius: 2px 2px 0 0;
	}
</style>
