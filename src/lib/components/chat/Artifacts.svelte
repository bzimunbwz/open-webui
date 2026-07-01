<script lang="ts">
	import { toast } from 'svelte-sonner';
	import { onMount, getContext, createEventDispatcher } from 'svelte';
	const i18n = getContext('i18n');
	const dispatch = createEventDispatcher();

	import {
		artifactCode,
		chatId,
		config,
		settings,
		showArtifacts,
		showControls,
		artifactContents
	} from '$lib/stores';
	import { copyToClipboard, createMessagesList } from '$lib/utils';
	import { injectCsp } from '$lib/utils/csp';

	import XMark from '../icons/XMark.svelte';
	import ArrowsPointingOut from '../icons/ArrowsPointingOut.svelte';
	import Tooltip from '../common/Tooltip.svelte';
	import SvgPanZoom from '../common/SVGPanZoom.svelte';
	import ArrowLeft from '../icons/ArrowLeft.svelte';
	import Download from '../icons/Download.svelte';

	export let overlay = false;

	let contents: Array<{ type: string; content: string }> = [];
	let selectedContentIdx = 0;

	let copied = false;
	let iframeElement: HTMLIFrameElement;

	function navigateContent(direction: 'prev' | 'next') {
		selectedContentIdx =
			direction === 'prev'
				? Math.max(selectedContentIdx - 1, 0)
				: Math.min(selectedContentIdx + 1, contents.length - 1);
	}

	const iframeLoadHandler = () => {
		iframeElement.contentWindow.addEventListener(
			'click',
			function (e) {
				const target = e.target.closest('a');
				if (target && target.href) {
					e.preventDefault();
					const url = new URL(target.href, iframeElement.baseURI);
					if (url.origin === window.location.origin) {
						iframeElement.contentWindow.history.pushState(
							null,
							'',
							url.pathname + url.search + url.hash
						);
					} else {
						console.info('External navigation blocked:', url.href);
					}
				}
			},
			true
		);

		// Cancel drag when hovering over iframe
		iframeElement.contentWindow.addEventListener('mouseenter', function (e) {
			e.preventDefault();
			iframeElement.contentWindow.addEventListener('dragstart', (event) => {
				event.preventDefault();
			});
		});
	};

	const showFullScreen = () => {
		if (iframeElement.requestFullscreen) {
			iframeElement.requestFullscreen();
		} else if (iframeElement.webkitRequestFullscreen) {
			iframeElement.webkitRequestFullscreen();
		} else if (iframeElement.msRequestFullscreen) {
			iframeElement.msRequestFullscreen();
		}
	};

	const downloadArtifact = () => {
		const blob = new Blob([contents[selectedContentIdx].content], { type: 'text/html' });
		const url = URL.createObjectURL(blob);
		const a = document.createElement('a');
		a.href = url;
		a.download = `artifact-${$chatId}-${selectedContentIdx}.html`;
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
		URL.revokeObjectURL(url);
	};

	const GW = 'https://webapp-2nd-service-production.up.railway.app';
	let sharing = false;
	const shareArtifact = async () => {
		const item = contents[selectedContentIdx];
		if (!item?.content) return;
		sharing = true;
		try {
			const res = await fetch(`${GW}/api/artifacts/share`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: item.content, type: item.type === 'svg' ? 'svg' : 'html' })
			});
			if (!res.ok) throw new Error(await res.text());
			const data = await res.json();
			const link = data.url || `${GW}${data.path}`;
			await navigator.clipboard.writeText(link);
			toast.success($i18n.t('Share link copied to clipboard'));
		} catch (e) {
			toast.error($i18n.t('Could not create share link'));
		}
		sharing = false;
	};

	onMount(() => {
		const unsubscribeArtifactCode = artifactCode.subscribe((value) => {
			if (contents) {
				const codeIdx = contents.findIndex((content) => content.content.includes(value));
				selectedContentIdx = codeIdx !== -1 ? codeIdx : 0;
			}
		});

		const unsubscribeArtifactContents = artifactContents.subscribe((value) => {
			const newContents = value ?? [];
			console.log('Artifact contents updated:', newContents);

			if (newContents.length === 0) {
				showControls.set(false);
				showArtifacts.set(false);
				selectedContentIdx = 0;
			} else if (newContents.length > contents.length) {
				selectedContentIdx = newContents.length - 1;
			}

			contents = newContents;
		});

		return () => {
			unsubscribeArtifactCode();
			unsubscribeArtifactContents();
		};
	});
</script>

<div
	class=" w-full h-full relative flex flex-col bg-white dark:bg-[#292929]"
	id="artifacts-container"
>
	<div class="w-full h-full flex flex-col flex-1 relative">
		{#if contents.length > 0}
			<div
				class="pointer-events-auto z-20 flex justify-between items-center gap-2 px-3 py-2 border-b border-black/5 dark:border-[#ffffff1a] dark:bg-[#161616] font-primary text-gray-900 dark:text-white"
			>
				<!-- Version navigation -->
				<div
					class="flex items-center gap-0.5 self-center min-w-fit rounded-[var(--radius-xl)] bg-black/5 dark:bg-white/5 p-0.5"
					dir="ltr"
				>
					<button
						class="self-center flex items-center justify-center size-7 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white transition disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
						on:click={() => navigateContent('prev')}
						disabled={contents.length <= 1}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="2.5"
							class="size-3.5"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
						</svg>
					</button>

					<div
						class="text-xs font-medium self-center min-w-fit px-1.5 tabular-nums text-gray-600 dark:text-gray-300"
					>
						{$i18n.t('Version {{selectedVersion}} of {{totalVersions}}', {
							selectedVersion: selectedContentIdx + 1,
							totalVersions: contents.length
						})}
					</div>

					<button
						class="self-center flex items-center justify-center size-7 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-white dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white transition disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-transparent"
						on:click={() => navigateContent('next')}
						disabled={contents.length <= 1}
					>
						<svg
							xmlns="http://www.w3.org/2000/svg"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							stroke-width="2.5"
							class="size-3.5"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
						</svg>
					</button>
				</div>

				<!-- Actions -->
				<div class="flex items-center gap-1">
					<button
						class="copy-code-button flex items-center justify-center text-xs font-medium px-3 h-7 rounded-lg bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-gray-700 dark:text-gray-200 transition"
						on:click={() => {
							copyToClipboard(contents[selectedContentIdx].content);
							copied = true;

							setTimeout(() => {
								copied = false;
							}, 2000);
						}}>{copied ? $i18n.t('Copied') : $i18n.t('Copy')}</button
					>

					<Tooltip content={$i18n.t('Download')}>
						<button
							class="flex items-center justify-center size-7 rounded-lg bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-gray-700 dark:text-gray-200 transition"
							on:click={downloadArtifact}
						>
							<Download className="size-3.5" />
						</button>
					</Tooltip>

					<Tooltip content={sharing ? $i18n.t('Creating link...') : $i18n.t('Share link')}>
						<button
							class="flex items-center justify-center size-7 rounded-lg bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-gray-700 dark:text-gray-200 transition disabled:opacity-50"
							on:click={shareArtifact}
							disabled={sharing}
						>
							<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.8" stroke="currentColor" class="size-3.5"><path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 1 0 0 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186 9.566-5.314m-9.566 7.5 9.566 5.314m0 0a2.25 2.25 0 1 0 3.935 2.186 2.25 2.25 0 0 0-3.935-2.186Zm0-12.814a2.25 2.25 0 1 0 3.933-2.185 2.25 2.25 0 0 0-3.933 2.185Z" /></svg>
						</button>
					</Tooltip>

					{#if contents[selectedContentIdx].type === 'iframe'}
						<Tooltip content={$i18n.t('Open in full screen')}>
							<button
								class="flex items-center justify-center size-7 rounded-lg bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-gray-700 dark:text-gray-200 transition"
								on:click={showFullScreen}
							>
								<ArrowsPointingOut className="size-3.5" />
							</button>
						</Tooltip>
					{/if}

					<div class="w-px h-5 bg-black/10 dark:bg-white/10 mx-0.5"></div>

					<Tooltip content={$i18n.t('Close')}>
						<button
							class="flex items-center justify-center size-7 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-black/5 dark:hover:bg-white/10 hover:text-gray-900 dark:hover:text-white transition"
							on:click={() => {
								dispatch('close');
								showControls.set(false);
								showArtifacts.set(false);
							}}
						>
							<XMark className="size-4" />
						</button>
					</Tooltip>
				</div>
			</div>
			{/if}

		{#if overlay}
			<div class=" absolute top-0 left-0 right-0 bottom-0 z-10"></div>
		{/if}

		<div class="flex-1 w-full h-full">
			<div class=" h-full flex flex-col">
				{#if contents.length > 0}
					<div class="max-w-full w-full h-full">
						{#if contents[selectedContentIdx].type === 'iframe'}
							<iframe
								bind:this={iframeElement}
								title="Content"
								srcdoc={injectCsp(
									contents[selectedContentIdx].content,
									$config?.ui?.iframe_csp ?? ''
								)}
								class="w-full border-0 h-full rounded-none"
								sandbox="allow-scripts allow-downloads{($settings?.iframeSandboxAllowForms ?? false)
									? ' allow-forms'
									: ''}{($settings?.iframeSandboxAllowSameOrigin ?? false)
									? ' allow-same-origin'
									: ''}"
								on:load={iframeLoadHandler}
							></iframe>
						{:else if contents[selectedContentIdx].type === 'svg'}
							<SvgPanZoom
								className=" w-full h-full max-h-full overflow-hidden"
								svg={contents[selectedContentIdx].content}
							/>
						{/if}
					</div>
				{:else}
					<div class="m-auto font-medium text-xs text-gray-900 dark:text-white">
						{$i18n.t('No HTML, CSS, or JavaScript content found.')}
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>
