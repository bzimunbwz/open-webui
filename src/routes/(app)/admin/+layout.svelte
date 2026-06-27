<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { goto } from '$app/navigation';

	import { WEBUI_NAME, config, mobile, showSidebar, user } from '$lib/stores';
	import { page } from '$app/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	import Sidebar from '$lib/components/icons/Sidebar.svelte';

	const i18n = getContext('i18n');

	let loaded = false;

	// Inline icons (lucide-style) keep the layout self-contained.
	const icons: Record<string, string> = {
		users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
		analytics: '<path d="M3 3v18h18"/><rect x="7" y="11" width="3" height="6" rx="1"/><rect x="12" y="7" width="3" height="10" rx="1"/><rect x="17" y="13" width="3" height="4" rx="1"/>',
		evaluations: '<path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>',
		functions: '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
		providers: '<rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><line x1="6" y1="6" x2="6.01" y2="6"/><line x1="6" y1="18" x2="6.01" y2="18"/>',
		packages: '<path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" y1="22" x2="12" y2="12"/>',
		coupons: '<path d="M2 9a3 3 0 0 1 0 6v2a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-2a3 3 0 0 1 0-6V7a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2z"/><path d="M13 5v2"/><path d="M13 17v2"/><path d="M13 11v2"/>',
		payments: '<rect x="2" y="5" width="20" height="14" rx="2"/><line x1="2" y1="10" x2="22" y2="10"/>',
		settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'
	};

	$: navItems = [
		{ href: '/admin', label: 'Users', path: '/admin', icon: 'users' },
		...($config?.features.enable_admin_analytics ?? true
			? [{ href: '/admin/analytics', label: 'Analytics', path: '/admin/analytics', icon: 'analytics' }]
			: []),
		{ href: '/admin/evaluations', label: 'Evaluations', path: '/admin/evaluations', icon: 'evaluations' },
		{ href: '/admin/functions', label: 'Functions', path: '/admin/functions', icon: 'functions' },
		{ href: '/admin/providers', label: 'Providers', path: '/admin/providers', icon: 'providers' },
		{ href: '/admin/packages', label: 'Packages', path: '/admin/packages', icon: 'packages' },
		{ href: '/admin/coupons', label: 'Coupons', path: '/admin/coupons', icon: 'coupons' },
		{ href: '/admin/payments', label: 'Payments', path: '/admin/payments', icon: 'payments' },
		{ href: '/admin/settings', label: 'Settings', path: '/admin/settings', icon: 'settings' }
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
		<!-- Top header tab nav -->
		<nav class="admin-nav px-2 sm:px-3 pt-2 backdrop-blur-xl drag-region select-none border-b border-white/[0.06]">
			<div class="flex items-center gap-1">
				{#if $mobile}
					<div class="{$showSidebar ? 'md:hidden' : ''} flex flex-none items-center self-end">
						<Tooltip content={$showSidebar ? $i18n.t('Close Sidebar') : $i18n.t('Open Sidebar')} interactive={true}>
							<button
								id="sidebar-toggle-button"
								class="cursor-pointer flex rounded-lg hover:bg-white/[0.06] transition"
								on:click={() => showSidebar.set(!$showSidebar)}
							>
								<div class="self-center p-1.5"><Sidebar /></div>
							</button>
						</Tooltip>
					</div>
				{/if}

				<div
					class="flex gap-0.5 scrollbar-none overflow-x-auto w-full text-sm font-medium"
					style="-webkit-overflow-scrolling: touch;"
				>
					{#each navItems as item}
						<a
							draggable="false"
							href={item.href}
							class="admin-nav-tab group flex items-center gap-2 min-w-fit px-3 py-2 rounded-t-lg transition-all duration-150 select-none relative
								{isActive(item.path)
									? 'text-white font-semibold admin-nav-tab-active'
									: 'text-gray-400 hover:text-gray-200 hover:bg-white/[0.04]'}"
						>
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
								class="size-4 flex-none {isActive(item.path) ? 'text-[#d4a574]' : 'text-gray-500 group-hover:text-gray-300'}"
							>
								{@html icons[item.icon]}
							</svg>
							<span>{$i18n.t(item.label)}</span>
						</a>
					{/each}
				</div>
			</div>
		</nav>

		<div class="pb-1 flex-1 min-h-0 overflow-y-auto">
			<slot />
		</div>
	</div>
{/if}

<style>
	/* ── Top nav active underline ───────────────────────────────── */
	.admin-nav-tab-active::after {
		content: '';
		position: absolute;
		bottom: 0;
		left: 8px;
		right: 8px;
		height: 2.5px;
		background: linear-gradient(90deg, #d4a574, #c4956a);
		border-radius: 3px 3px 0 0;
	}

	/* ── Shared admin theme (applies across every admin page) ────── */
	:global(.admin-panel) {
		--admin-accent: #d4a574;
		--admin-accent-strong: #c4956a;
	}

	:global(.admin-panel .admin-settings-tabs-container) {
		gap: 0.25rem;
	}
	:global(.admin-panel .admin-settings-tabs-container button),
	:global(.admin-panel .admin-settings-tabs-container a) {
		border-radius: 0.625rem;
		transition: background-color 0.15s ease, color 0.15s ease;
	}

	:global(.admin-panel input:not([type='checkbox']):not([type='radio'])),
	:global(.admin-panel select),
	:global(.admin-panel textarea) {
		border-radius: 0.625rem;
	}
	:global(.admin-panel input:not([type='checkbox']):not([type='radio']):focus),
	:global(.admin-panel select:focus),
	:global(.admin-panel textarea:focus) {
		outline: none;
		border-color: var(--admin-accent);
		box-shadow: 0 0 0 1px rgba(212, 165, 116, 0.35);
	}

	:global(.admin-panel .rounded-xl),
	:global(.admin-panel .rounded-2xl) {
		border-radius: 1rem;
	}

	:global(.admin-panel)::-webkit-scrollbar,
	:global(.admin-panel *)::-webkit-scrollbar {
		width: 8px;
		height: 8px;
	}
	:global(.admin-panel)::-webkit-scrollbar-thumb,
	:global(.admin-panel *)::-webkit-scrollbar-thumb {
		background: rgba(255, 255, 255, 0.08);
		border-radius: 8px;
	}
</style>
