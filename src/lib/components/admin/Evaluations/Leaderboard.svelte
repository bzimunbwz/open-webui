<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { models } from '$lib/stores';
	import { getLeaderboard } from '$lib/apis/evaluations';
	import ModelModal from './LeaderboardModal.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Search from '$lib/components/icons/Search.svelte';
	import ChevronUp from '$lib/components/icons/ChevronUp.svelte';
	import ChevronDown from '$lib/components/icons/ChevronDown.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	const i18n = getContext('i18n');

	let rankedModels = [];
	let query = '';
	let loading = true;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let orderBy = 'rating';
	let direction: 'asc' | 'desc' = 'desc';

	let showModal = false;
	let selectedModel = null;

	const toggleSort = (key: string) => {
		if (orderBy === key) {
			direction = direction === 'asc' ? 'desc' : 'asc';
		} else {
			orderBy = key;
			direction = key === 'name' ? 'asc' : 'desc';
		}
	};

	const openModal = (model) => {
		selectedModel = model;
		showModal = true;
	};

	const closeModal = () => {
		selectedModel = null;
		showModal = false;
	};

	const loadLeaderboard = async (searchQuery = '') => {
		loading = true;
		try {
			const result = await getLeaderboard(localStorage.token, searchQuery);
			const statsMap = new Map((result?.entries ?? []).map((e) => [e.model_id, e]));

			rankedModels = $models
				.filter((m) => m?.owned_by !== 'arena' && !m?.info?.meta?.hidden)
				.map((model) => {
					const s = statsMap.get(model.id);
					return {
						...model,
						rating: s?.rating ?? '-',
						stats: {
							count: s ? s.won + s.lost : 0,
							won: s?.won?.toString() ?? '-',
							lost: s?.lost?.toString() ?? '-'
						},
						top_tags: s?.top_tags ?? []
					};
				})
				.sort((a, b) => {
					if (a.rating === '-') return 1;
					if (b.rating === '-') return -1;
					return b.rating - a.rating;
				});
		} catch (err) {
			console.error('Leaderboard load failed:', err);
		}
		loading = false;
	};

	const debouncedLoad = () => {
		loading = true;
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => loadLeaderboard(query), 500);
	};

	$: if (query !== null) {
		debouncedLoad();
	}

	$: sortedModels = [...rankedModels].sort((a, b) => {
		const getValue = (m, key) => {
			if (key === 'name') return m.name ?? m.id ?? '';
			if (key === 'rating') return m.rating === '-' ? -Infinity : m.rating;
			if (key === 'won' || key === 'lost') {
				const v = m.stats[key];
				return v === '-' ? -Infinity : Number(v);
			}
			return 0;
		};
		const aVal = getValue(a, orderBy);
		const bVal = getValue(b, orderBy);
		if (orderBy === 'name') {
			return direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
		}
		return direction === 'asc' ? aVal - bVal : bVal - aVal;
	});

	const medal = (rank: number) => (rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : '');

	const columns = [
		{ key: 'rating', label: 'RK', class: 'w-12' },
		{ key: 'name', label: 'Model', class: '' },
		{ key: 'rating', label: 'Rating', class: 'text-right' },
		{ key: 'won', label: 'Won', class: 'text-right w-20' },
		{ key: 'lost', label: 'Lost', class: 'text-right w-20' }
	];
</script>

<ModelModal bind:show={showModal} model={selectedModel} onClose={closeModal} />

<div class="w-full">
	<div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
		<div class="flex items-center gap-2.5">
			<h1 class="text-xl font-semibold text-gray-900 dark:text-white">{$i18n.t('Leaderboard')}</h1>
			<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-black/5 dark:bg-white/10 text-gray-600 dark:text-gray-300">
				{rankedModels.length}
			</span>
		</div>

		<Tooltip content={$i18n.t('Re-rank models by topic similarity')}>
			<div class="flex items-center w-full sm:w-64 px-3 py-1.5 rounded-xl bg-gray-100 dark:bg-gray-850 border border-gray-200 dark:border-gray-800 focus-within:border-[#d4a574] transition">
				<Search className="size-3.5 text-gray-400 flex-none" />
				<input class="w-full text-sm ml-2 outline-hidden bg-transparent" bind:value={query} placeholder={$i18n.t('Search')} />
			</div>
		</Tooltip>
	</div>

	<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-hidden relative min-h-[120px]">
		{#if loading}
			<div class="absolute inset-0 flex items-center justify-center z-10 bg-white/50 dark:bg-gray-900/50">
				<Spinner className="size-5" />
			</div>
		{/if}

		{#if !rankedModels.length && !loading}
			<div class="text-center text-sm text-gray-500 py-12">{$i18n.t('No models found')}</div>
		{:else if rankedModels.length}
			<div class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full">
				<table class="w-full text-sm text-left text-gray-600 dark:text-gray-300 {loading ? 'opacity-20' : ''}">
					<thead class="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-850/60">
						<tr class="border-b border-gray-200 dark:border-gray-800">
							{#each columns as col}
								<th scope="col" class="px-4 py-3 cursor-pointer select-none font-semibold {col.class}" on:click={() => toggleSort(col.key)}>
									<div class="flex gap-1.5 items-center {col.class.includes('right') ? 'justify-end' : ''}">
										{$i18n.t(col.label)}
										{#if orderBy === col.key}
											{#if direction === 'asc'}<ChevronUp className="size-2" />{:else}<ChevronDown className="size-2" />{/if}
										{:else}
											<span class="invisible"><ChevronUp className="size-2" /></span>
										{/if}
									</div>
								</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each sortedModels as model, idx (model.id)}
							{@const rank = model.rating !== '-' ? idx + 1 : null}
							<tr class="border-b border-gray-100 dark:border-gray-850/60 last:border-0 group cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-850/40 transition" on:click={() => openModal(model)}>
								<td class="px-4 py-2.5 font-semibold text-gray-900 dark:text-white">
									{#if rank && rank <= 3}
										<span class="text-base">{medal(rank)}</span>
									{:else}
										{rank ?? '-'}
									{/if}
								</td>
								<td class="px-4 py-2.5">
									<div class="flex items-center gap-2.5">
										<img src="{WEBUI_API_BASE_URL}/models/model/profile/image?id={model.id}" alt={model.name} class="size-6 rounded-full object-cover shrink-0" on:error={(e) => { e.target.src = '/favicon.png'; }} />
										<Tooltip content={`${model.name} (${model.id})`} placement="top-start">
											<span class="font-medium text-gray-800 dark:text-gray-200 line-clamp-1">{model.name}</span>
										</Tooltip>
									</div>
								</td>
								<td class="px-4 py-2.5 text-right">
									{#if model.rating === '-'}
										<span class="text-gray-400">-</span>
									{:else}
										<span class="inline-block font-semibold text-gray-900 dark:text-white px-2 py-0.5 rounded-lg bg-[#d4a574]/15">{model.rating}</span>
									{/if}
								</td>
								<td class="px-4 py-2.5 text-right font-medium text-green-500">
									{#if model.stats.won === '-'}-{:else}
										<span class="hidden group-hover:inline">{((Number(model.stats.won) / model.stats.count) * 100).toFixed(1)}%</span>
										<span class="group-hover:hidden">{model.stats.won}</span>
									{/if}
								</td>
								<td class="px-4 py-2.5 text-right font-medium text-red-500">
									{#if model.stats.lost === '-'}-{:else}
										<span class="hidden group-hover:inline">{((Number(model.stats.lost) / model.stats.count) * 100).toFixed(1)}%</span>
										<span class="group-hover:hidden">{model.stats.lost}</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	</div>

	<div class="text-gray-500 text-xs mt-3 w-full flex justify-end">
		<div class="text-right">
			<div class="line-clamp-1">
				ⓘ {$i18n.t('The evaluation leaderboard is based on the Elo rating system and is updated in real-time.')}
			</div>
			{$i18n.t('The leaderboard is currently in beta, and we may adjust the rating calculations as we refine the algorithm.')}
		</div>
	</div>
</div>
