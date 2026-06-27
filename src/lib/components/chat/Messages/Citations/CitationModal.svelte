<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';
	import Modal from '$lib/components/common/Modal.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import { WEBUI_API_BASE_URL } from '$lib/constants';
	import { settings, config } from '$lib/stores';
	import { injectCsp } from '$lib/utils/csp';

	import XMark from '$lib/components/icons/XMark.svelte';
	import Textarea from '$lib/components/common/Textarea.svelte';

	const i18n = getContext('i18n');

	const CONTENT_PREVIEW_LIMIT = 10000;
	let expandedDocs: Set<number> = new Set();

	export let show = false;
	export let citation;
	export let showPercentage = false;
	export let showRelevance = true;

	let mergedDocuments = [];

	function calculatePercentage(distance: number) {
		if (typeof distance !== 'number') return null;
		if (distance < 0) return 0;
		if (distance > 1) return 100;
		return Math.round(distance * 10000) / 100;
	}

	function getRelevanceColor(percentage: number) {
		if (percentage >= 80)
			return 'bg-green-200 dark:bg-green-800 text-green-800 dark:text-green-200';
		if (percentage >= 60)
			return 'bg-yellow-200 dark:bg-yellow-800 text-yellow-800 dark:text-yellow-200';
		if (percentage >= 40)
			return 'bg-orange-200 dark:bg-orange-800 text-orange-800 dark:text-orange-200';
		return 'bg-red-200 dark:bg-red-800 text-red-800 dark:text-red-200';
	}

	$: if (citation) {
		expandedDocs = new Set();
		mergedDocuments = citation.document?.map((c, i) => {
			return {
				source: citation.source,
				document: c,
				metadata: citation.metadata?.[i],
				distance: citation.distances?.[i]
			};
		});
		if (mergedDocuments.every((doc) => doc.distance !== undefined)) {
			mergedDocuments = mergedDocuments.sort(
				(a, b) => (b.distance ?? Infinity) - (a.distance ?? Infinity)
			);
		}
	}

	const decodeString = (str: string) => {
		try {
			return decodeURIComponent(str);
		} catch {
			return str;
		}
	};

	const getDomain = (url: string) => {
		try {
			return new URL(url).hostname.replace(/^www\./, '');
		} catch {
			return url;
		}
	};

	function computeHeadUrl(c, docs) {
		const u = docs?.[0]?.source?.url ?? c?.source?.url ?? '';
		if (typeof u === 'string' && u.includes('http')) return u;
		const n = c?.source?.name;
		if (typeof n === 'string' && n.startsWith('http')) return n;
		return '';
	}

	$: headUrl = computeHeadUrl(citation, mergedDocuments);
	$: headFileId = mergedDocuments?.[0]?.metadata?.file_id ?? '';
	$: headPage = Number.isInteger(mergedDocuments?.[0]?.metadata?.page)
		? mergedDocuments[0].metadata.page + 1
		: null;

	const getTextFragmentUrl = (doc: any): string | null => {
		const { metadata, source, document: content } = doc ?? {};
		const { file_id, page } = metadata ?? {};
		const sourceUrl = source?.url;

		const baseUrl = file_id
			? `${WEBUI_API_BASE_URL}/files/${file_id}/content${page !== undefined ? `#page=${page + 1}` : ''}`
			: sourceUrl?.includes('http')
				? sourceUrl
				: null;

		if (!baseUrl || !content) return baseUrl;

		// Extract first and last words for text fragment, filtering out URLs and emojis
		const words = content
			.trim()
			.replace(/\s+/g, ' ')
			.split(' ')
			.filter((w: string) => w.length > 0 && !/https?:\/\/|[\u{1F300}-\u{1F9FF}]/u.test(w));

		if (words.length === 0) return baseUrl;

		const clean = (w: string) => w.replace(/[^\w]/g, '');
		const first = clean(words[0]);
		const last = clean(words.at(-1));
		const fragment = words.length === 1 ? first : `${first},${last}`;

		return fragment ? `${baseUrl}#:~:text=${fragment}` : baseUrl;
	};
</script>

<Modal size="lg" bind:show>
	<div>
			<div class="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-gray-100 dark:border-white/10 dark:text-gray-200">
				<div class="flex items-start gap-3 min-w-0">
					{#if headUrl}
						<img
							src="https://www.google.com/s2/favicons?sz=64&domain={headUrl}"
							alt=""
							class="size-9 rounded-[var(--radius-xl)] shrink-0 bg-white border border-gray-100 dark:border-white/10 p-1 object-contain"
							on:error={(e) => {
								e.target.src = '/favicon.png';
							}}
						/>
					{:else}
						<div class="size-9 rounded-[var(--radius-xl)] shrink-0 bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-gray-400">
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="size-4.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
						</div>
					{/if}
					<div class="min-w-0">
						<div class="text-base font-semibold text-gray-900 dark:text-white line-clamp-2">
							{citation?.source?.name ? decodeString(citation.source.name) : $i18n.t('Citation')}
						</div>
						{#if headUrl}
							<a
								href={headUrl}
								target="_blank"
								class="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 underline line-clamp-1"
							>
								{getDomain(headUrl)}
							</a>
						{:else if headFileId}
							<a
								href={`${WEBUI_API_BASE_URL}/files/${headFileId}/content`}
								target="_blank"
								class="text-xs text-gray-500 dark:text-gray-400 underline"
							>
								{$i18n.t('Open file')}
							</a>
						{/if}
						<div class="flex items-center gap-1.5 mt-1.5 flex-wrap text-[11px] font-medium text-gray-400">
							<span class="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800">
								{mergedDocuments.length}
								{mergedDocuments.length === 1 ? $i18n.t('document') : $i18n.t('documents')}
							</span>
							{#if headPage}
								<span class="px-1.5 py-0.5 rounded-md bg-gray-100 dark:bg-gray-800">{$i18n.t('page')} {headPage}</span>
							{/if}
							{#if showRelevance && showPercentage && mergedDocuments?.[0]?.distance !== undefined}
								{@const pct = calculatePercentage(mergedDocuments[0].distance)}
								{#if typeof pct === 'number'}
									<span class={`px-1.5 py-0.5 rounded-md ${getRelevanceColor(pct)}`}>{pct.toFixed(0)}% {$i18n.t('Relevance')}</span>
								{/if}
							{/if}
						</div>
					</div>
				</div>
				<div class="flex items-center gap-1 shrink-0">
					{#if headUrl}
						<a
							href={headUrl}
							target="_blank"
							class="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 transition text-gray-500"
							aria-label={$i18n.t('Open link')}
						>
							<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="size-4"><path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>
						</a>
					{/if}
					<button
						class="p-1.5 rounded-lg hover:bg-black/5 dark:hover:bg-white/10 transition"
						aria-label={$i18n.t('Close citation modal')}
						on:click={() => {
							show = false;
						}}
					>
						<XMark className={'size-5'} />
					</button>
				</div>
			</div>

		<div class="flex flex-col md:flex-row w-full px-5 pb-5 md:space-x-4">
			<div
				class="flex flex-col w-full dark:text-gray-200 overflow-y-scroll max-h-[22rem] scrollbar-thin gap-1"
			>
				{#each mergedDocuments as document, documentIdx}
					<div class="flex flex-col w-full gap-2">
						{#if document.metadata?.parameters}
							<div>
								<div class="text-sm font-medium dark:text-gray-300 mb-1">
									{$i18n.t('Parameters')}
								</div>

								<Textarea readonly value={JSON.stringify(document.metadata.parameters, null, 2)}
								></Textarea>
							</div>
						{/if}

						<div>
							<div
								class=" text-sm font-medium dark:text-gray-300 flex items-center gap-2 w-fit mb-1"
							>
								{#if document.source?.url?.includes('http')}
									{@const snippetUrl = getTextFragmentUrl(document)}
									{#if snippetUrl}
										<a
											href={snippetUrl}
											target="_blank"
											class="underline hover:text-gray-500 dark:hover:text-gray-100"
											>{$i18n.t('Content')}</a
										>
									{:else}
										{$i18n.t('Content')}
									{/if}
								{:else}
									{$i18n.t('Content')}
								{/if}

								{#if showRelevance && document.distance !== undefined}
									<Tooltip
										className="w-fit"
										content={$i18n.t('Relevance')}
										placement="top-start"
										tippyOptions={{ duration: [500, 0] }}
									>
										<div class="text-sm my-1 dark:text-gray-400 flex items-center gap-2 w-fit">
											{#if showPercentage}
												{@const percentage = calculatePercentage(document.distance)}

												{#if typeof percentage === 'number'}
													<span
														class={`px-1 rounded-sm font-medium ${getRelevanceColor(percentage)}`}
													>
														{percentage.toFixed(2)}%
													</span>
												{/if}
											{:else if typeof document?.distance === 'number'}
												<span class="text-gray-500 dark:text-gray-500">
													({(document?.distance ?? 0).toFixed(4)})
												</span>
											{/if}
										</div>
									</Tooltip>
								{/if}

								{#if Number.isInteger(document?.metadata?.page)}
									<span class="text-sm text-gray-500 dark:text-gray-400">
										({$i18n.t('page')}
										{document.metadata.page + 1})
									</span>
								{/if}
							</div>

							{#if document.metadata?.html}
								<iframe
									class="w-full border-0 h-auto rounded-none"
									sandbox="allow-scripts allow-forms{($settings?.iframeSandboxAllowSameOrigin ??
									false)
										? ' allow-same-origin'
										: ''}"
									srcdoc={injectCsp(document.document, $config?.ui?.iframe_csp ?? '')}
									title={$i18n.t('Content')}
								></iframe>
							{:else}
								{@const rawContent = document.document.trim().replace(/\n\n+/g, '\n\n')}
								{@const isTruncated =
									($settings?.renderMarkdownInPreviews ?? true) &&
									rawContent.length > CONTENT_PREVIEW_LIMIT &&
									!expandedDocs.has(documentIdx)}
								{#if $settings?.renderMarkdownInPreviews ?? true}
									<div
										class="text-sm prose dark:prose-invert markdown-prose-sm min-w-full max-w-full"
									>
										<Markdown
											content={isTruncated
												? rawContent.slice(0, CONTENT_PREVIEW_LIMIT)
												: rawContent}
											id="citation-{documentIdx}"
										/>
									</div>
									{#if isTruncated}
										<button
											class="mt-1 text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
											on:click={() => {
												expandedDocs.add(documentIdx);
												expandedDocs = expandedDocs;
											}}
										>
											{$i18n.t('Show all ({{COUNT}} characters)', {
												COUNT: rawContent.length.toLocaleString()
											})}
										</button>
									{/if}
								{:else}
									<pre class="text-sm dark:text-gray-400 whitespace-pre-line">{rawContent}</pre>
								{/if}
							{/if}
						</div>
					</div>
				{/each}
			</div>
		</div>
	</div>
</Modal>
