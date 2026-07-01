<script lang="ts">
	import { onMount, onDestroy, getContext } from 'svelte';
	import { slide } from 'svelte/transition';
	import { user } from '$lib/stores';

	const i18n = getContext('i18n');
	const GW = 'https://webapp-2nd-service-production.up.railway.app';

	let warn: any = null; // worst limit at >=90%
	let dismissedKey = '';
	let timer: any;

	const fmtReset = (x: number) => {
		x = Math.max(0, Math.floor(x || 0));
		if (x >= 86400) return `${Math.floor(x / 86400)}d ${Math.floor((x % 86400) / 3600)}h`;
		if (x >= 3600) return `${Math.floor(x / 3600)}h ${Math.floor((x % 3600) / 60)}m`;
		return `${Math.max(1, Math.floor(x / 60))}m`;
	};

	async function check() {
		try {
			const res = await fetch(`${GW}/api/usage?_=${Date.now()}`, {
				headers: { 'X-User-Email': $user?.email || '' }
			});
			const data = await res.json();
			let worst: any = null;
			for (const l of data?.limits ?? []) {
				if (l.limit > 0) {
					const p = Math.round((l.used / l.limit) * 100);
					if (p >= 90 && (!worst || p > worst.pct)) worst = { ...l, pct: Math.min(100, p) };
				}
			}
			warn = worst;
		} catch (e) {
			/* silent */
		}
	}

	onMount(() => {
		check();
		timer = setInterval(check, 60000);
	});
	onDestroy(() => clearInterval(timer));

	$: warnKey = warn ? `${warn.key}-${warn.pct}` : '';
</script>

{#if warn && dismissedKey !== warnKey}
	<div
		transition:slide={{ duration: 250 }}
		class="mx-1 mb-2 flex items-center gap-2.5 px-3.5 py-2 rounded-[var(--radius-xl)] border text-xs {warn.pct >=
		100
			? 'border-red-500/30 bg-red-500/10 text-red-600 dark:text-red-400'
			: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300'}"
	>
		<svg
			xmlns="http://www.w3.org/2000/svg"
			viewBox="0 0 24 24"
			fill="currentColor"
			class="size-4 shrink-0"
		>
			<path
				fill-rule="evenodd"
				d="M9.401 3.003c1.155-2 4.043-2 5.197 0l7.355 12.748c1.154 2-.29 4.5-2.599 4.5H4.645c-2.309 0-3.752-2.5-2.598-4.5L9.4 3.003ZM12 8.25a.75.75 0 0 1 .75.75v3.75a.75.75 0 0 1-1.5 0V9a.75.75 0 0 1 .75-.75Zm0 8.25a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Z"
				clip-rule="evenodd"
			/>
		</svg>
		<div class="flex-1 min-w-0">
			{#if warn.pct >= 100}
				{$i18n.t('You have reached your')} <b>{warn.label}</b> {$i18n.t('limit')} ({warn.used.toLocaleString()}/{warn.limit.toLocaleString()}
				{warn.unit}) · {$i18n.t('resets in')}
				{fmtReset(warn.resets_in_seconds)}.
			{:else}
				{$i18n.t("You've used")} <b>{warn.pct}%</b> {$i18n.t('of your')}
				{warn.label.toLowerCase()} ({warn.used.toLocaleString()}/{warn.limit.toLocaleString()}
				{warn.unit}) · {$i18n.t('resets in')}
				{fmtReset(warn.resets_in_seconds)}.
			{/if}
			<a href="/subscription" class="underline font-medium ml-1">{$i18n.t('Upgrade')}</a>
		</div>
		<button
			class="shrink-0 opacity-70 hover:opacity-100 transition"
			aria-label={$i18n.t('Dismiss')}
			on:click={() => (dismissedKey = warnKey)}
		>
			<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-4"
				><path
					d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z"
				/></svg
			>
		</button>
	</div>
{/if}
