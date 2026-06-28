<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';
	import { createAPIKey, getAPIKey } from '$lib/apis/auths';

	const i18n = getContext('i18n');

	const API_BASE = 'https://claudesk.pro/api';
	const MODEL = 'claude-opus-4.8';

	let apiKey = '';
	let loading = false;
	let revealed = false;

	$: key = apiKey || 'YOUR_API_KEY';

	let activeTab: 'claude-code' | 'openai' | 'codex' = 'claude-code';

	const tabs = [
		{ id: 'claude-code', label: 'Claude Code' },
		{ id: 'openai', label: 'OpenAI-Compatible' },
		{ id: 'codex', label: 'Codex CLI' }
	];

	onMount(async () => {
		try {
			apiKey = (await getAPIKey(localStorage.token)) || '';
		} catch (e) {
			apiKey = '';
		}
	});

	const generate = async () => {
		loading = true;
		try {
			const k = await createAPIKey(localStorage.token);
			if (k) {
				apiKey = k;
				revealed = true;
				toast.success($i18n.t('API key generated'));
			} else {
				toast.error($i18n.t('Failed to generate API key'));
			}
		} catch (e) {
			toast.error($i18n.t('Failed to generate API key'));
		}
		loading = false;
	};

	let copiedId = '';
	const copy = (id: string, text: string) => {
		navigator.clipboard.writeText(text);
		copiedId = id;
		setTimeout(() => (copiedId = ''), 1500);
	};

	// ---- snippets (reactive on key) ----
	$: claudeRouterConfig = `{
  "Providers": [
    {
      "name": "claudesk",
      "api_base_url": "${API_BASE}/chat/completions",
      "api_key": "${key}",
      "models": ["claude-opus-4.8", "claude-sonnet-4.6"]
    }
  ],
  "Router": {
    "default": "claudesk,claude-opus-4.8"
  }
}`;

	$: continueConfig = `{
  "models": [
    {
      "title": "ClaudeSK",
      "provider": "openai",
      "model": "${MODEL}",
      "apiBase": "${API_BASE}",
      "apiKey": "${key}"
    }
  ]
}`;

	$: curlSnippet = `curl ${API_BASE}/chat/completions \\
  -H "Authorization: Bearer ${key}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "${MODEL}",
    "messages": [{ "role": "user", "content": "Hello!" }]
  }'`;

	$: codexConfig = `[model_providers.claudesk]
name = "ClaudeSK"
base_url = "${API_BASE}"
env_key = "CLAUDESK_API_KEY"
wire_api = "chat"

[profiles.claudesk]
model = "${MODEL}"
model_provider = "claudesk"`;

	$: codexEnv = `export CLAUDESK_API_KEY="${key}"`;
</script>

<svelte:head><title>{$i18n.t('CLI Docs')}</title></svelte:head>

<div class="h-full w-full overflow-y-auto">
	<div class="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
		<!-- Header -->
		<div class="mb-6">
			<h1 class="text-2xl font-bold text-gray-900 dark:text-white">{$i18n.t('CLI Docs')}</h1>
			<p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
				{$i18n.t('Use your ClaudeSK models in your terminal and code editors. Generate an API key and copy a config below.')}
			</p>
		</div>

		<!-- API key card -->
		<div class="rounded-[var(--radius-xl)] border border-gray-200 dark:border-[#ffffff1a] bg-white dark:bg-[#1a1a1a] p-4 sm:p-5 mb-6">
			<div class="flex items-center justify-between gap-3 mb-2">
				<div class="text-sm font-semibold text-gray-900 dark:text-white">{$i18n.t('Your API Key')}</div>
				<button
					class="text-xs font-semibold px-3 py-1.5 rounded-lg bg-[#d4a574] text-white hover:bg-[#c79560] transition disabled:opacity-50"
					on:click={generate}
					disabled={loading}
				>
					{loading ? $i18n.t('Generating...') : apiKey ? $i18n.t('Regenerate Key') : $i18n.t('Generate Key')}
				</button>
			</div>
			<div class="flex items-center gap-2">
				<code class="flex-1 min-w-0 truncate text-xs font-mono px-3 py-2 rounded-lg bg-gray-100 dark:bg-[#292929] text-gray-800 dark:text-gray-200 border border-gray-200 dark:border-[#ffffff1a]">
					{apiKey ? (revealed ? apiKey : apiKey.slice(0, 10) + '••••••••••••') : $i18n.t('No key yet — click Generate Key')}
				</code>
				{#if apiKey}
					<button class="text-xs px-2.5 py-2 rounded-lg border border-gray-200 dark:border-[#ffffff1a] text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/10 transition" on:click={() => (revealed = !revealed)}>
						{revealed ? $i18n.t('Hide') : $i18n.t('Show')}
					</button>
					<button class="text-xs px-2.5 py-2 rounded-lg border border-gray-200 dark:border-[#ffffff1a] text-gray-600 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-white/10 transition" on:click={() => copy('key', apiKey)}>
						{copiedId === 'key' ? $i18n.t('Copied') : $i18n.t('Copy')}
					</button>
				{/if}
			</div>
			<div class="mt-2 text-[11px] text-gray-500 dark:text-gray-400">
				{$i18n.t('Base URL')}: <code class="font-mono">{API_BASE}</code> · {$i18n.t('Keep this key secret. Regenerating invalidates the old key.')}
			</div>
		</div>

		<!-- Tabs -->
		<div class="flex items-center gap-1 p-0.5 rounded-[var(--radius-xl)] bg-gray-100 dark:bg-white/5 w-fit mb-5 overflow-x-auto">
			{#each tabs as t}
				<button
					class="text-sm font-medium px-4 py-1.5 rounded-lg transition whitespace-nowrap {activeTab === t.id ? 'bg-[#d4a574] text-white shadow-sm' : 'text-gray-600 dark:text-gray-300 hover:bg-white dark:hover:bg-white/10'}"
					on:click={() => (activeTab = t.id)}
				>
					{t.label}
				</button>
			{/each}
		</div>

		<!-- Panels -->
		{#if activeTab === 'claude-code'}
			<div class="space-y-4">
				<p class="text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('Claude Code speaks the Anthropic API, so we use Claude Code Router to bridge it to ClaudeSK. Follow these steps:')}
				</p>
				<ol class="space-y-4 text-sm text-gray-800 dark:text-gray-200 list-decimal pl-5">
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Install Claude Code and the router')}</div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">npm install -g @anthropic-ai/claude-code @musistudio/claude-code-router</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('cc-install', 'npm install -g @anthropic-ai/claude-code @musistudio/claude-code-router')}>{copiedId === 'cc-install' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Create')} <code class="font-mono text-xs">~/.claude-code-router/config.json</code></div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">{claudeRouterConfig}</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('cc-config', claudeRouterConfig)}>{copiedId === 'cc-config' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Start Claude Code through the router')}</div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">ccr code</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('cc-run', 'ccr code')}>{copiedId === 'cc-run' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
				</ol>
			</div>
		{:else if activeTab === 'openai'}
			<div class="space-y-4">
				<p class="text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('Works with any OpenAI-compatible tool (Cline, Roo Code, Continue, Cursor custom models, LibreChat, etc.). Use these values:')}
				</p>
				<div class="rounded-lg border border-gray-200 dark:border-[#ffffff1a] divide-y divide-gray-200 dark:divide-[#ffffff1a] text-sm">
					<div class="flex justify-between gap-3 px-3 py-2"><span class="text-gray-500 dark:text-gray-400">{$i18n.t('Base URL')}</span><code class="font-mono text-gray-800 dark:text-gray-200">{API_BASE}</code></div>
					<div class="flex justify-between gap-3 px-3 py-2"><span class="text-gray-500 dark:text-gray-400">{$i18n.t('API Key')}</span><code class="font-mono text-gray-800 dark:text-gray-200 truncate max-w-[60%]">{key}</code></div>
					<div class="flex justify-between gap-3 px-3 py-2"><span class="text-gray-500 dark:text-gray-400">{$i18n.t('Model')}</span><code class="font-mono text-gray-800 dark:text-gray-200">{MODEL}</code></div>
				</div>

				<div>
					<div class="font-medium text-sm text-gray-800 dark:text-gray-200 mb-1.5">{$i18n.t('Continue')} (<code class="font-mono text-xs">~/.continue/config.json</code>)</div>
					<div class="relative">
						<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">{continueConfig}</pre>
						<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('cont', continueConfig)}>{copiedId === 'cont' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
					</div>
				</div>

				<div>
					<div class="font-medium text-sm text-gray-800 dark:text-gray-200 mb-1.5">{$i18n.t('Quick test')} (curl)</div>
					<div class="relative">
						<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">{curlSnippet}</pre>
						<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('curl', curlSnippet)}>{copiedId === 'curl' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
					</div>
				</div>
				<p class="text-[11px] text-gray-500 dark:text-gray-400">
					{$i18n.t('In Cline / Roo Code / Cursor: choose the "OpenAI Compatible" provider, then paste the Base URL, API Key and Model above.')}
				</p>
			</div>
		{:else}
			<div class="space-y-4">
				<p class="text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('Add ClaudeSK as a custom model provider for the OpenAI Codex CLI.')}
				</p>
				<ol class="space-y-4 text-sm text-gray-800 dark:text-gray-200 list-decimal pl-5">
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Add this to')} <code class="font-mono text-xs">~/.codex/config.toml</code></div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">{codexConfig}</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('codex-cfg', codexConfig)}>{copiedId === 'codex-cfg' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Set your API key in the environment')}</div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">{codexEnv}</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('codex-env', codexEnv)}>{copiedId === 'codex-env' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
					<li>
						<div class="font-medium mb-1.5">{$i18n.t('Run Codex with the profile')}</div>
						<div class="relative">
							<pre class="text-xs font-mono p-3 rounded-lg bg-[#1a1a1a] text-gray-200 overflow-x-auto border border-[#ffffff1a]">codex --profile claudesk</pre>
							<button class="absolute top-2 right-2 text-[11px] px-2 py-1 rounded bg-white/10 hover:bg-white/20 text-gray-200" on:click={() => copy('codex-run', 'codex --profile claudesk')}>{copiedId === 'codex-run' ? $i18n.t('Copied') : $i18n.t('Copy')}</button>
						</div>
					</li>
				</ol>
			</div>
		{/if}
	</div>
</div>
