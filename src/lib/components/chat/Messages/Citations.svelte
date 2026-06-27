<script lang="ts">
	import { getContext } from 'svelte';
	import { embed, showControls, showEmbeds } from '$lib/stores';

	import CitationModal from './Citations/CitationModal.svelte';
	import { fly, fade } from 'svelte/transition';
	import { quintOut } from 'svelte/easing';

	const i18n = getContext('i18n');

	export let id = '';
	export let chatId = '';

	export let sources = [];
	export let readOnly = false;

	let citations = [];
	let showPercentage = false;
	let showRelevance = true;

	let citationModal = null;

	let showCitations = false;
	let showCitationModal = false;

	let selectedCitation: any = null;

	export const showSourceModal = (sourceId) => {
		let index;
		let suffix = null;

		if (typeof sourceId === 'string') {
			const output = sourceId.split('#');
			index = parseInt(output[0]) - 1;

			if (output.length > 1) {
				suffix = output[1];
			}
		} else {
			index = sourceId - 1;
		}

		if (citations[index]) {
			console.log('Showing citation modal for:', citations[index]);

			if (citations[index]?.source?.embed_url) {
				const embedUrl = citations[index].source.embed_url;
				if (embedUrl) {
					if (readOnly) {
						// Open in new tab if readOnly
						window.open(embedUrl, '_blank');
						return;
					} else {
						showControls.set(true);
						showEmbeds.set(true);
						embed.set({
							url: embedUrl,
							title: citations[index]?.source?.name || 'Embedded Content',
							source: citations[index],
							chatId: chatId,
							messageId: id,
							sourceId: sourceId
						});
					}
				} else {
					selectedCitation = citations[index];
					showCitationModal = true;
				}
			} else {
				selectedCitation = citations[index];
				showCitationModal = true;
			}
		}
	};

	function calculateShowRelevance(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		const inRange = distances.filter((d) => d !== undefined && d >= -1 && d <= 1).length;
		const outOfRange = distances.filter((d) => d !== undefined && (d < -1 || d > 1)).length;

		if (distances.length === 0) {
			return false;
		}

		if (
			(inRange === distances.length - 1 && outOfRange === 1) ||
			(outOfRange === distances.length - 1 && inRange === 1)
		) {
			return false;
		}

		return true;
	}

	function shouldShowPercentage(sources: any[]) {
		const distances = sources.flatMap((citation) => citation.distances ?? []);
		return distances.every((d) => d !== undefined && d >= -1 && d <= 1);
	}

	$: {
		citations = sources.reduce((acc, source) => {
			if (Object.keys(source).length === 0) {
				return acc;
			}

			source?.document?.forEach((document, index) => {
				const metadata = source?.metadata?.[index];
				const distance = source?.distances?.[index];

				// Within the same citation there could be multiple documents
				const id = metadata?.source ?? source?.source?.id ?? 'N/A';
				let _source = source?.source;

				if (metadata?.name) {
					_source = { ..._source, name: metadata.name };
				}

				if (id.startsWith('http://') || id.startsWith('https://')) {
					_source = { ..._source, name: id, url: id };
				}

				const existingSource = acc.find((item) => item.id === id);

				if (existingSource) {
					existingSource.document.push(document);
					existingSource.metadata.push(metadata);
					if (distance !== undefined) existingSource.distances.push(distance);
				} else {
					acc.push({
						id: id,
						source: _source,
						document: [document],
						metadata: metadata ? [metadata] : [],
						distances: distance !== undefined ? [distance] : []
					});
				}
			});

			return acc;
		}, []);
		console.log('citations', citations);

		showRelevance = calculateShowRelevance(citations);
		showPercentage = shouldShowPercentage(citations);
	}

	const decodeString = (str: string) => {
		try {
			return decodeURIComponent(str);
		} catch (e) {
			return str;
		}
	};

	const getDomain = (url: string) => {
		try {
			return new URL(url).hostname.replace(/^www\./, '');
		} catch (e) {
			return url;
		}
	};

	const portal = (node: HTMLElement) => {
		document.body.appendChild(node);
		return {
			destroy() {
				if (node.parentNode) node.parentNode.removeChild(node);
			}
		};
	};
</script>

<CitationModal
	bind:show={showCitationModal}
	citation={selectedCitation}
	{showPercentage}
	{showRelevance}
/>

{#if citations.length > 0}
	{@const urlCitations = citations.filter((c) => c?.source?.name?.startsWith('http'))}
	<div class=" py-1 -mx-0.5 w-full flex gap-1 items-center flex-wrap">
		<button
			class="text-xs font-medium text-gray-600 dark:text-gray-300 px-3.5 h-8 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition flex items-center gap-1 border border-gray-50 dark:border-gray-850/30"
			aria-label={citations.length === 1
				? $i18n.t('Toggle 1 source')
				: $i18n.t('Toggle {{COUNT}} sources', { COUNT: citations.length })}
			aria-expanded={showCitations}
			on:click={() => {
				showCitations = !showCitations;
			}}
		>
			{#if urlCitations.length > 0}
				<div class="flex -space-x-1 items-center">
					{#each urlCitations.slice(0, 3) as citation, idx}
						<img
							src="https://www.google.com/s2/favicons?sz=32&domain={citation.source.name}"
							alt="favicon"
							class="size-4 rounded-full shrink-0 border border-white dark:border-gray-850 bg-white dark:bg-gray-900"
							on:error={(e) => {
								e.target.src = '/favicon.png';
							}}
						/>
					{/each}
					{#if citations.length > 3}
						<div
							class="size-4 rounded-full shrink-0 border border-white dark:border-gray-850 bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-[8px] font-semibold text-gray-500 dark:text-gray-400 whitespace-nowrap tracking-tighter"
							aria-hidden="true"
						>
							+{citations.length - Math.min(urlCitations.length, 3)}
						</div>
					{/if}
				</div>
			{/if}
			<div>
				{#if citations.length === 1}
					{$i18n.t('1 Source')}
				{:else}
					{$i18n.t('{{COUNT}} Sources', {
						COUNT: citations.length
					})}
				{/if}
			</div>
		</button>
	</div>
{/if}

{#if showCitations}
	<!-- Backdrop -->
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		class="fixed inset-0 z-[9998] bg-black/30 dark:bg-black/50"
		use:portal
		transition:fade={{ duration: 200 }}
		on:click={() => (showCitations = false)}
	></div>

	<!-- Right-side sources tray -->
	<div
		class="fixed top-0 right-0 bottom-0 z-[9999] w-full sm:max-w-[26rem] bg-white dark:bg-[#1c1c1b] border-l border-gray-100 dark:border-white/10 shadow-2xl flex flex-col"
		use:portal
		transition:fly={{ x: 460, duration: 380, easing: quintOut }}
	>
		<div class="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-white/10 shrink-0">
			<div class="flex items-center gap-2">
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="size-4 text-gray-500"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
				<h2 class="text-base font-semibold text-gray-900 dark:text-white">
					{$i18n.t('{{COUNT}} Sources', { COUNT: citations.length })}
				</h2>
			</div>
			<button
				class="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 transition"
				on:click={() => (showCitations = false)}
				aria-label={$i18n.t('Close')}
			>
				<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" class="size-5 text-gray-500"><path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z"/></svg>
			</button>
		</div>

		<div class="flex-1 overflow-y-auto px-3.5 py-3.5 flex flex-col gap-2.5">
			{#each citations as citation, idx}
				{@const isUrl = citation?.source?.name?.startsWith('http')}
				{@const url = citation?.source?.url || citation?.source?.name || ''}
				{@const snippet = (citation?.document?.[0] ?? '').toString()}
				<button
					id={`source-${id}-${idx + 1}`}
					aria-label={$i18n.t('View source: {{name}}', { name: decodeString(citation.source.name) })}
					class="group text-left rounded-2xl border border-gray-100 dark:border-white/10 bg-transparent hover:bg-black/[0.03] dark:hover:bg-white/[0.04] hover:border-gray-200 dark:hover:border-white/20 transition p-3.5 flex flex-col gap-2"
					on:click={() => {
						showCitationModal = true;
						selectedCitation = citation;
					}}
				>
					<div class="flex items-center gap-2.5 min-w-0 w-full">
						{#if isUrl}
							<img
								src="https://www.google.com/s2/favicons?sz=64&domain={citation.source.name}"
								alt=""
								class="size-5 rounded-md shrink-0 bg-white"
								on:error={(e) => {
									e.target.src = '/favicon.png';
								}}
							/>
						{:else}
							<div class="size-5 rounded-md shrink-0 bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-[10px] font-semibold text-gray-500">
								{idx + 1}
							</div>
						{/if}
						<div class="min-w-0 flex-1">
							<div class="text-sm font-medium text-gray-900 dark:text-gray-100 group-hover:text-black dark:group-hover:text-white truncate transition">
								{decodeString(citation.source.name)}
							</div>
							{#if isUrl}
								<div class="text-[11px] text-gray-400 truncate">{getDomain(url)}</div>
							{/if}
						</div>
						<div class="text-[11px] font-medium text-gray-400 shrink-0">#{idx + 1}</div>
					</div>
					{#if snippet}
						<div class="text-xs text-gray-500 dark:text-gray-400 line-clamp-3 leading-relaxed">
							{snippet}
						</div>
					{/if}
				</button>
			{/each}
		</div>
	</div>
{/if}
