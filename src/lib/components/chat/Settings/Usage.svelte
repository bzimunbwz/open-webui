<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { user } from '$lib/stores';

	const i18n = getContext('i18n');

	const GW = 'https://webapp-2nd-service-production.up.railway.app';

	let loading = true;
	let refreshing = false;
	let error = '';
	let data: any = null;

	const fmtNum = (n: number) => (n ?? 0).toLocaleString();
	const fmtReset = (s: number) => {
		s = Math.max(0, Math.floor(s || 0));
		if (s >= 86400) return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
		if (s >= 3600) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
		return `${Math.max(1, Math.floor(s / 60))}m`;
	};
	const pct = (used: number, limit: number) =>
		limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0;

	async function load() {
		refreshing = true;
		error = '';
		try {
			// cache-buster so limits/resets always reflect the latest values
			const res = await fetch(`${GW}/api/usage?_=${Date.now()}`, {
				headers: { 'X-User-Email': $user?.email || '' }
			});
			data = await res.json();
		} catch (e) {
			error = 'Could not load usage right now.';
		}
		loading = false;
		refreshing = false;
	}

	onMount(load);
</script>

<div class="flex flex-col h-full text-sm" id="tab-usage">
	<div class="flex items-center justify-between gap-2 mb-1">
		<div class="flex items-center gap-2 min-w-0">
			<div class="text-lg font-medium text-gray-900 dark:text-white">{$i18n.t('Usage')}</div>
			{#if data?.package}
				<span
					class="text-[11px] font-bold px-2 py-0.5 rounded-full bg-[#d4a574]/20 text-[#d4a574] uppercase tracking-wide"
					>{data.package}</span
				>
			{/if}
		</div>
		<button
			on:click={load}
			disabled={refreshing}
			class="shrink-0 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200 dark:border-[#ffffff1a] text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/10 transition disabled:opacity-50"
		>
			<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" class="size-3.5 {refreshing ? 'animate-spin' : ''}"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182m0-4.991v4.99" /></svg>
			{refreshing ? $i18n.t('Refreshing...') : $i18n.t('Refresh')}
		</button>
	</div>
	<div class="text-xs text-gray-500 dark:text-gray-400 mb-5">
		{$i18n.t('Your plan limits and how much you have used.')}
	</div>

	{#if loading}
		<div class="text-gray-500 dark:text-gray-400">{$i18n.t('Loading...')}</div>
	{:else if error}
		<div class="text-red-500">{error}</div>
	{:else if data?.limits}
		<div class="flex flex-col gap-5">
			{#each data.limits as l}
				<div>
					<div class="flex items-end justify-between mb-1.5 gap-3">
						<div class="min-w-0">
							<div class="font-medium text-gray-900 dark:text-white">{$i18n.t(l.label)}</div>
							<div class="text-xs text-gray-500 dark:text-gray-400">
								{#if l.limit}
									{fmtNum(l.used)} / {fmtNum(l.limit)} {l.unit}
								{:else}
									{fmtNum(l.used)} {l.unit} · {$i18n.t('unlimited')}
								{/if}
								{#if l.used > 0}
									· {$i18n.t('resets in')} {fmtReset(l.resets_in_seconds)}{/if}
							</div>
						</div>
						<div class="text-sm font-semibold text-gray-700 dark:text-gray-300 shrink-0">
							{l.limit ? `${pct(l.used, l.limit)}% ${$i18n.t('used')}` : '∞'}
						</div>
					</div>
					<div class="w-full h-2 rounded-full bg-gray-200 dark:bg-gray-800 overflow-hidden">
						<div
							class="h-full rounded-full transition-all {pct(l.used, l.limit) >= 90
								? 'bg-red-500'
								: 'bg-[#d4a574]'}"
							style="width: {l.limit ? pct(l.used, l.limit) : 0}%"
						></div>
					</div>
				</div>
			{/each}
		</div>
		<div class="text-[11px] text-gray-400 dark:text-gray-500 mt-6">
			{$i18n.t('Limits are set by your subscription plan. Upgrade for higher limits.')}
		</div>
	{/if}
</div>
