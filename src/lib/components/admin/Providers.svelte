<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	// ── Safe localStorage wrapper (Firefox blocks it in some modes) ───
	function lsGet(key: string): string {
		try { return localStorage.getItem(key) || ''; } catch { return ''; }
	}
	function lsSet(key: string, val: string) {
		try { localStorage.setItem(key, val); } catch { /* ignored */ }
	}

	// ── Gateway connection ─────────────────────────────────────────────
	function normalizeUrl(url: string): string {
		url = url.trim().replace(/\/+$/, '');
		if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
			url = 'https://' + url;
		}
		return url;
	}
	const DEFAULT_GATEWAY_URL = 'https://webapp-2nd-service-production.up.railway.app';
	const DEFAULT_GATEWAY_KEY = 'sk-gateway-admin';
	let savedUrl = normalizeUrl(lsGet('gateway_url'));
	// Use saved URL only if it contains 'webapp-2nd-service', otherwise use default
	let GATEWAY_URL = (savedUrl && savedUrl.includes('webapp-2nd-service')) ? savedUrl : DEFAULT_GATEWAY_URL;
	let GATEWAY_ADMIN_KEY = lsGet('gateway_admin_key') || DEFAULT_GATEWAY_KEY;
	let showGatewayConfig = false;
	let connected = false;

	// ── Data ───────────────────────────────────────────────────────────
	let providers: any[] = [];
	let providerHealth: any = {};
	let loading = true;

	// ── UI state ──────────────────────────────────────────────────────
	let showAddProvider = false;
	let expandedProviders: Record<string, boolean> = {};
	let bulkUploadTarget = '';
	let bulkText = '';
	let searchQuery = '';

	// New provider form
	let newProvider = {
		id: '', name: '', base_url: '', api_keys: [''],
		description: '', docs_url: '', tier: 'free'
	};

	// ── Known provider templates ──────────────────────────────────────
	const PROVIDER_TEMPLATES: Record<string, any> = {
		freemodel: {
			name: 'FreeModel.dev',
			base_url: 'https://api.freemodel.dev/v1',
			description: 'OpenAI-compatible provider. Add multiple API keys — requests automatically fall back to the next key on failure.',
			docs_url: 'https://freemodel.dev/dashboard/docs',
			icon: '✦'
		},
		freellmapi: {
			name: 'FreeLLMAPI',
			base_url: '',
			description: 'Self-hosted proxy aggregating 16+ free LLM providers behind one /v1 endpoint.',
			docs_url: 'https://github.com/tashfeenahmed/freellmapi',
			icon: '☁'
		},
		llm7: {
			name: 'LLM7',
			base_url: 'https://api.llm7.io/v1',
			description: 'OpenAI-compatible provider. Add multiple API keys — requests automatically fall back to the next key on failure. Get free keys at token.llm7.io.',
			docs_url: 'https://docs.llm7.io/quickstart',
			icon: '☁'
		},
		zai: {
			name: 'Z.AI',
			base_url: 'https://api.z.ai/api/paas/v4/',
			description: 'OpenAI-compatible provider at https://api.z.ai/api/paas/v4. Add multiple API keys — requests automatically fall back to the next key on failure.',
			docs_url: 'https://docs.z.ai/guides/overview/quick-start',
			icon: '☁'
		},
		zenmux: {
			name: 'ZenMux',
			base_url: '',
			description: 'Multi-provider router.',
			docs_url: '',
			icon: '☁'
		}
	};

	// ── API helpers ───────────────────────────────────────────────────

	async function gw(path: string, method = 'GET', body?: any) {
		let res: Response;
		try {
			res = await fetch(`${GATEWAY_URL}${path}`, {
				method,
				headers: {
					'Content-Type': 'application/json',
					'Authorization': `Bearer ${GATEWAY_ADMIN_KEY}`
				},
				...(body ? { body: JSON.stringify(body) } : {})
			});
		} catch (e: any) {
			throw new Error(`Cannot reach gateway at ${GATEWAY_URL} — check the URL and that the service is running`);
		}
		const text = await res.text();
		if (!res.ok) throw new Error(`${res.status}: ${text}`);
		try {
			return JSON.parse(text);
		} catch {
			throw new Error(`Gateway returned non-JSON (status ${res.status}). Got: ${text.substring(0, 200)}`);
		}
	}

	// ── Load ──────────────────────────────────────────────────────────

	async function loadAll() {
		if (!GATEWAY_URL || !GATEWAY_ADMIN_KEY) {
			showGatewayConfig = true;
			loading = false;
			return;
		}
		loading = true;
		try {
			const config = await gw('/admin/config');
			const health = await gw('/admin/providers');
			providerHealth = health.providers || {};

			providers = Object.entries(config.providers || {}).map(([id, p]: [string, any]) => {
				const tmpl = PROVIDER_TEMPLATES[id] || {};
				return {
					id,
					name: p.name || tmpl.name || id,
					base_url: p.base_url || tmpl.base_url || '',
					api_keys: p.api_keys || [],
					description: tmpl.description || '',
					docs_url: tmpl.docs_url || '',
					icon: tmpl.icon || '☁',
					health: providerHealth[id] || {},
					models: [], // populated by sync
					enabledModels: new Set(),
				};
			});

			connected = true;
			// Auto-expand all
			providers.forEach(p => { expandedProviders[p.id] = true; });
		} catch (e: any) {
			toast.error(`Connection failed: ${e.message}`);
			connected = false;
		}
		loading = false;
	}

	// ── Provider CRUD ─────────────────────────────────────────────────

	async function saveProvider(p: any) {
		try {
			await gw(`/admin/providers/${p.id}`, 'PUT', {
				name: p.name,
				base_url: p.base_url,
				api_keys: p.api_keys.filter((k: string) => k.trim()),
			});
			toast.success(`${p.name} saved`);
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function createProvider() {
		if (!newProvider.id || !newProvider.name) {
			toast.error('ID and Name are required');
			return;
		}
		try {
			await gw('/admin/providers', 'POST', {
				id: newProvider.id,
				name: newProvider.name,
				base_url: newProvider.base_url,
				api_keys: newProvider.api_keys.filter((k: string) => k.trim()),
			});
			toast.success(`${newProvider.name} created`);
			newProvider = { id: '', name: '', base_url: '', api_keys: [''], description: '', docs_url: '', tier: 'free' };
			showAddProvider = false;
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function deleteProvider(id: string, name: string) {
		if (!confirm(`Delete provider "${name}"? Models using it will lose this backend.`)) return;
		try {
			await gw(`/admin/providers/${id}`, 'DELETE');
			toast.success(`${name} deleted`);
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function resetProvider(id: string) {
		try {
			await gw(`/admin/providers/${id}/reset`, 'POST');
			toast.success('Provider reset');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	// ── Key management ────────────────────────────────────────────────

	function addKey(provider: any) {
		provider.api_keys = [...provider.api_keys, ''];
		providers = providers;
	}

	function removeKey(provider: any, idx: number) {
		provider.api_keys = provider.api_keys.filter((_: any, i: number) => i !== idx);
		providers = providers;
	}

	function maskKey(key: string): string {
		if (!key || key.length < 12) return '••••••••';
		return key.slice(0, 8) + ' ... ' + key.slice(-4);
	}

	async function bulkAddKeys() {
		const keys = bulkText.split('\n').map(k => k.trim()).filter(k => k && !k.startsWith('#'));
		if (!keys.length) { toast.error('No valid keys'); return; }

		const provider = providers.find(p => p.id === bulkUploadTarget);
		if (!provider) return;

		const allKeys = [...new Set([...provider.api_keys, ...keys])];
		try {
			await gw(`/admin/providers/${provider.id}`, 'PUT', {
				name: provider.name,
				base_url: provider.base_url,
				api_keys: allKeys,
			});
			toast.success(`Added ${keys.length} keys to ${provider.name}`);
			bulkText = '';
			bulkUploadTarget = '';
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	// ── Sync models from provider ─────────────────────────────────────

	async function syncModels(provider: any) {
		if (!provider.base_url) {
			toast.error('No base URL configured');
			return;
		}
		try {
			const data = await gw(`/admin/providers/${provider.id}/models`);
			provider.models = (data.data || data.models || []).map((m: any) => ({
				id: m.id,
				name: m.name || m.id,
				owned_by: m.owned_by || '',
				context_length: m.context_length || m.context_window || null,
				capabilities: {
					tools: m.capabilities?.tools || false,
					vision: m.capabilities?.vision || false,
				},
			}));
			providers = providers;
			toast.success(`Loaded ${provider.models.length} models from ${provider.name}`);
		} catch (e: any) {
			toast.error(`Sync failed: ${e.message}`);
		}
	}

	// ── Gateway config ────────────────────────────────────────────────

	function saveGatewayConfig() {
		// Normalize URL: add https:// if missing, remove trailing slash
		let url = GATEWAY_URL.trim();
		if (url && !url.startsWith('http://') && !url.startsWith('https://')) {
			url = 'https://' + url;
		}
		GATEWAY_URL = url.replace(/\/+$/, '');
		lsSet('gateway_url', GATEWAY_URL);
		lsSet('gateway_admin_key', GATEWAY_ADMIN_KEY);
		showGatewayConfig = false;
		loadAll();
	}

	// ── Template selector ─────────────────────────────────────────────

	function applyTemplate(templateId: string) {
		const tmpl = PROVIDER_TEMPLATES[templateId];
		if (tmpl) {
			newProvider.id = templateId;
			newProvider.name = tmpl.name;
			newProvider.base_url = tmpl.base_url;
			newProvider.description = tmpl.description;
			newProvider.docs_url = tmpl.docs_url;
		}
	}

	onMount(() => { loadAll(); });
</script>

<!-- ══════════════════════════════════════════════════════════════════ -->

<div class="flex flex-col h-full overflow-y-auto">
	<!-- Header -->
	<div class="px-6 pt-5 pb-3">
		<div class="flex items-center justify-between mb-1">
			<h1 class="text-2xl font-bold">Providers</h1>
			<div class="flex items-center gap-2">
				<button
					on:click={() => (showGatewayConfig = !showGatewayConfig)}
					class="text-xs text-gray-400 hover:text-gray-200 transition px-2 py-1"
				>
					{#if connected}
						<span class="inline-block w-2 h-2 rounded-full bg-green-500 mr-1"></span>Gateway
					{:else}
						<span class="inline-block w-2 h-2 rounded-full bg-red-500 mr-1"></span>Disconnected
					{/if}
				</button>
				<button
					on:click={loadAll}
					class="text-xs px-3 py-1.5 bg-gray-800 rounded-lg hover:bg-gray-700 transition"
				>Refresh</button>
				<button
					on:click={() => (showAddProvider = true)}
					class="text-xs px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition flex items-center gap-1"
				>
					<span class="text-sm">+</span> Add Provider
				</button>
			</div>
		</div>
		<p class="text-sm text-gray-500">Manage AI model providers and toggle individual models</p>
	</div>

	<!-- Gateway Config Banner -->
	{#if showGatewayConfig}
		<div class="mx-6 mb-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
			<h3 class="text-sm font-semibold mb-3">Gateway Connection</h3>
			<div class="flex gap-3 mb-3">
				<div class="flex-1">
					<label class="text-xs text-gray-400 mb-1 block">Gateway URL</label>
					<input bind:value={GATEWAY_URL} placeholder="https://your-gateway.up.railway.app"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div class="flex-1">
					<label class="text-xs text-gray-400 mb-1 block">Admin Key</label>
					<input type="password" bind:value={GATEWAY_ADMIN_KEY} placeholder="sk-gateway-admin"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
			</div>
			<button on:click={saveGatewayConfig}
				class="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition">
				Connect
			</button>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="animate-spin w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full"></div>
		</div>
	{:else if connected}

		<!-- Add Provider Form -->
		{#if showAddProvider}
			<div class="mx-6 mb-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
				<div class="flex items-center justify-between mb-3">
					<h3 class="text-sm font-semibold">Add New Provider</h3>
					<div class="flex gap-1">
						{#each Object.entries(PROVIDER_TEMPLATES) as [tid, tmpl]}
							<button on:click={() => applyTemplate(tid)}
								class="text-xs px-2 py-1 bg-gray-800 rounded hover:bg-gray-700 transition">
								{tmpl.name}
							</button>
						{/each}
					</div>
				</div>
				<div class="grid grid-cols-3 gap-3 mb-3">
					<div>
						<label class="text-xs text-gray-400 mb-1 block">Provider ID</label>
						<input bind:value={newProvider.id} placeholder="e.g. freemodel"
							class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
					</div>
					<div>
						<label class="text-xs text-gray-400 mb-1 block">Display Name</label>
						<input bind:value={newProvider.name} placeholder="e.g. FreeModel.dev"
							class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
					</div>
					<div>
						<label class="text-xs text-gray-400 mb-1 block">Base URL</label>
						<input bind:value={newProvider.base_url} placeholder="https://api.provider.com/v1"
							class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
					</div>
				</div>
				<div class="mb-3">
					<label class="text-xs text-gray-400 mb-1 block">API Keys (one per line)</label>
					<textarea
						bind:value={newProvider.api_keys[0]}
						placeholder="sk-key-1"
						rows="2"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono"
					></textarea>
				</div>
				<div class="flex gap-2">
					<button on:click={createProvider} class="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition">Create</button>
					<button on:click={() => (showAddProvider = false)} class="px-4 py-2 bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
				</div>
			</div>
		{/if}

		<!-- ══ ALL PROVIDERS LIST ══════════════════════════════════════ -->
		<div class="flex flex-col gap-4 px-6 pb-6">
			{#each providers as provider (provider.id)}
				<div class="bg-gray-900/50 rounded-2xl border border-gray-800 overflow-hidden">

					<!-- Provider Header -->
					<button
						class="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/50 transition cursor-pointer"
						on:click={() => { expandedProviders[provider.id] = !expandedProviders[provider.id]; }}
					>
						<div class="flex items-center gap-3">
							<span class="text-lg">{PROVIDER_TEMPLATES[provider.id]?.icon || '☁'}</span>
							<div class="text-left">
								<h2 class="font-semibold text-base">{provider.name}</h2>
								<span class="text-xs text-gray-500 font-mono">{provider.base_url || 'Not configured'}</span>
							</div>
						</div>

						<div class="flex items-center gap-3">
							<!-- Health badge -->
							{#if provider.health?.in_cooldown}
								<span class="text-xs px-2 py-0.5 rounded-full bg-red-900/40 text-red-400">Cooldown</span>
							{:else if provider.health?.failures > 0}
								<span class="text-xs px-2 py-0.5 rounded-full bg-yellow-900/40 text-yellow-400">{provider.health.failures} failures</span>
							{:else}
								<span class="text-xs px-2 py-0.5 rounded-full bg-green-900/40 text-green-400">Healthy</span>
							{/if}

							<!-- Key count -->
							<span class="text-xs text-gray-500">{provider.api_keys.length} key{provider.api_keys.length !== 1 ? 's' : ''}</span>

							<!-- Expand arrow -->
							<svg class="w-4 h-4 text-gray-500 transition-transform {expandedProviders[provider.id] ? 'rotate-180' : ''}"
								xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
								<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
							</svg>
						</div>
					</button>

					{#if expandedProviders[provider.id]}
						<div class="border-t border-gray-800">

							<!-- Config Section -->
							<div class="px-5 py-4 bg-gray-900/80">
								<div class="flex items-start gap-4">
									<!-- Config card -->
									<div class="flex-1 bg-gray-800/60 rounded-xl p-4 border border-gray-700/50">
										<div class="flex items-center gap-2 mb-2">
											<span class="text-gray-400">⚙</span>
											<h3 class="font-semibold text-sm">{provider.name} Configuration</h3>
										</div>
										{#if PROVIDER_TEMPLATES[provider.id]?.description}
											<p class="text-xs text-gray-500 mb-3">
												{PROVIDER_TEMPLATES[provider.id].description}
												{#if PROVIDER_TEMPLATES[provider.id]?.docs_url}
													<a href={PROVIDER_TEMPLATES[provider.id].docs_url} target="_blank" class="text-orange-400 hover:text-orange-300 ml-1">Docs →</a>
												{/if}
											</p>
										{/if}

										<!-- Base URL -->
										<div class="mb-3">
											<label class="text-xs text-gray-400 mb-1 block">Base URL</label>
											<input bind:value={provider.base_url}
												class="w-full rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm font-mono" />
										</div>

										<!-- Bulk key textarea -->
										<div class="mb-3">
											<label class="text-xs text-gray-400 mb-1 block">Paste one or more API keys — one per line</label>
											<div class="flex gap-2">
												<textarea
													placeholder="Paste one or more {provider.name} API keys — one per line"
													rows="2"
													bind:value={bulkText}
													on:focus={() => { bulkUploadTarget = provider.id; }}
													class="flex-1 rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm font-mono"
												></textarea>
												<div class="flex flex-col gap-1">
													<input placeholder="Label (optional)"
														class="rounded-lg border border-gray-600 bg-gray-900 px-3 py-2 text-sm w-40" />
												</div>
											</div>
										</div>

										<div class="flex gap-2 mb-4">
											<button on:click={() => { bulkUploadTarget = provider.id; bulkAddKeys(); }}
												class="px-3 py-1.5 bg-orange-600 text-white text-xs rounded-lg hover:bg-orange-700 transition flex items-center gap-1">
												<span>+</span> Add Keys
											</button>
											<button on:click={() => syncModels(provider)}
												class="px-3 py-1.5 bg-gray-700 text-xs rounded-lg hover:bg-gray-600 transition flex items-center gap-1">
												↻ Sync Models
											</button>
										</div>

										<!-- Existing keys -->
										{#if provider.api_keys.length > 0}
											<div class="flex flex-col gap-1.5">
												{#each provider.api_keys as key, i}
													<div class="flex items-center gap-2 bg-gray-900/80 rounded-lg px-3 py-2 border border-gray-700/50">
														<span class="text-xs text-gray-500 font-mono flex-1">{maskKey(key)}</span>
														<span class="text-xs text-gray-600">{i + 1}</span>
														<button class="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition"
															on:click={async () => {
																try {
																	// Quick test: hit /models with this key
																	const headers: any = { 'Authorization': `Bearer ${key}` };
																	const res = await fetch(`${provider.base_url.replace(/\/$/, '')}/models`, { headers });
																	if (res.ok) toast.success(`Key #${i+1} is valid`);
																	else toast.error(`Key #${i+1} returned ${res.status}`);
																} catch { toast.error(`Key #${i+1} connection failed`); }
															}}>Test</button>
														<button class="text-xs px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition">Disable</button>
														<button class="text-red-500 hover:text-red-400 transition"
															on:click={() => { removeKey(provider, i); saveProvider(provider); }}>
															<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
																<path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" />
															</svg>
														</button>
													</div>
												{/each}
											</div>
										{/if}
									</div>
								</div>

								<!-- Action buttons -->
								<div class="flex items-center justify-between mt-3">
									<div class="flex gap-2">
										<button on:click={() => saveProvider(provider)}
											class="text-xs px-3 py-1.5 bg-green-700 text-white rounded-lg hover:bg-green-600 transition">Save Config</button>
										<button on:click={() => resetProvider(provider.id)}
											class="text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition">Reset Health</button>
									</div>
									<button on:click={() => deleteProvider(provider.id, provider.name)}
										class="text-xs px-3 py-1.5 text-red-400 hover:text-red-300 transition">Delete Provider</button>
								</div>
							</div>

							<!-- Models Section -->
							{#if provider.models && provider.models.length > 0}
								<div class="border-t border-gray-800">
									<!-- Model toolbar -->
									<div class="px-5 py-3 flex items-center gap-3 bg-gray-900/40">
										<div class="flex-1 relative">
											<input
												bind:value={searchQuery}
												placeholder="Search {provider.name} models..."
												class="w-full rounded-lg border border-gray-700 bg-gray-800 pl-8 pr-3 py-1.5 text-sm"
											/>
											<svg class="absolute left-2.5 top-2 w-3.5 h-3.5 text-gray-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
												<path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" />
											</svg>
										</div>
										<button class="text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition flex items-center gap-1">
											<span>👁</span> Enable All
										</button>
										<button class="text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition flex items-center gap-1">
											<span>👁</span> Disable All
										</button>
										<button on:click={() => syncModels(provider)}
											class="text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition flex items-center gap-1">
											↻ Refresh
										</button>
									</div>

									<div class="px-5 py-1 text-xs text-gray-500">
										{provider.models.length} models available
									</div>

									<!-- Model list -->
									<div class="divide-y divide-gray-800/50">
										{#each provider.models.filter(m => !searchQuery || m.name.toLowerCase().includes(searchQuery.toLowerCase()) || m.id.toLowerCase().includes(searchQuery.toLowerCase())) as model}
											<div class="px-5 py-3 flex items-center justify-between hover:bg-gray-800/30 transition">
												<div>
													<div class="font-medium text-sm">{model.name}</div>
													<div class="text-xs text-orange-400 font-mono">{model.id}</div>
												</div>
												<div class="flex items-center gap-2">
													<!-- Badges -->
													<span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 uppercase">
														{model.owned_by || provider.name}
													</span>
													{#if model.context_length}
														<span class="text-[10px] px-2 py-0.5 rounded-full bg-gray-700 text-gray-300">
															{model.context_length >= 1000000
																? `${(model.context_length / 1000000).toFixed(1)}M CTX`
																: model.context_length >= 1000
																	? `${Math.round(model.context_length / 1000)}K CTX`
																	: `${model.context_length} CTX`}
														</span>
													{/if}
													{#if model.capabilities?.tools}
														<span class="text-[10px] px-2 py-0.5 rounded-full bg-purple-900/40 text-purple-400">⚡ TOOLS</span>
													{/if}
													{#if model.capabilities?.vision}
														<span class="text-[10px] px-2 py-0.5 rounded-full bg-blue-900/40 text-blue-400">👁 VISION</span>
													{/if}

													<!-- Toggle -->
													<button
														class="w-10 h-5 rounded-full transition relative {provider.enabledModels.has(model.id) ? 'bg-orange-500' : 'bg-gray-600'}"
														on:click={() => {
															if (provider.enabledModels.has(model.id)) {
																provider.enabledModels.delete(model.id);
															} else {
																provider.enabledModels.add(model.id);
															}
															providers = providers;
														}}
													>
														<span class="absolute top-0.5 {provider.enabledModels.has(model.id) ? 'right-0.5' : 'left-0.5'} w-4 h-4 rounded-full bg-white transition-all shadow"></span>
													</button>
												</div>
											</div>
										{/each}
									</div>
								</div>
							{:else}
								<div class="px-5 py-4 text-center border-t border-gray-800">
									<p class="text-sm text-gray-500 mb-2">No models loaded. Click "Sync Models" to fetch from this provider.</p>
									<button on:click={() => syncModels(provider)}
										class="text-xs px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition">
										↻ Sync Models
									</button>
								</div>
							{/if}

						</div>
					{/if}
				</div>
			{/each}

			{#if providers.length === 0}
				<div class="text-center py-16">
					<p class="text-gray-400 mb-2">No providers configured yet.</p>
					<button on:click={() => (showAddProvider = true)}
						class="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition">
						+ Add Your First Provider
					</button>
				</div>
			{/if}
		</div>
	{/if}
</div>

<!-- Bulk Upload Modal -->
{#if bulkUploadTarget && bulkText}
	<!-- handled inline now -->
{/if}
