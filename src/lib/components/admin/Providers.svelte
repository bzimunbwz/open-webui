<script lang="ts">
	import { getGatewayUrl } from '$lib/gateway';
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { slide } from 'svelte/transition';
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
	const DEFAULT_GATEWAY_URL = getGatewayUrl();
	const DEFAULT_GATEWAY_KEY = 'sk-gateway-admin';
	let savedUrl = normalizeUrl(lsGet('gateway_url'));
	let GATEWAY_URL = savedUrl || DEFAULT_GATEWAY_URL;
	let GATEWAY_ADMIN_KEY = lsGet('gateway_admin_key') || DEFAULT_GATEWAY_KEY;
	let showGatewayConfig = false;
	let connected = false;

	// ── Data ───────────────────────────────────────────────────────────
	let providers: any[] = [];
	let providerHealth: any = {};
	let facadeModels: any[] = [];
	let loading = true;

	// ── UI state ──────────────────────────────────────────────────────
	let showAddProvider = false;
	let showAddFacadeModel = false;
	let editingModel: any = null;
	let expandedProviders: Record<string, boolean> = {};
	let bulkUploadTarget = '';
	let bulkText = '';
	let bulkAccountsText = '';
	let cfAccountId = '';
	let cfAccountKey = '';
	let searchQuery = '';
	let modelSearchQuery = '';
	let activeTab: 'providers' | 'models' = 'providers';
	let savingEnabled = false;
	let hasUnsavedChanges = false;

	// Per-provider UI state (so bulk-key paste + model search stay isolated
	// per card instead of sharing one global textarea).
	let providerSearch: Record<string, string> = {};
	let bulkByProvider: Record<string, string> = {};

	// New provider form
	let newProvider = {
		id: '', name: '', base_url: '', api_keys: [''],
		description: '', docs_url: '', tier: 'free'
	};

	// New facade model form
	let newFacadeModel = {
		id: '', name: '', tier: 'free', backends: [{ provider: '', model: '' }]
	};

	// ── Model tier lookup (cross-reference with facade models) ───────
	function getModelTier(providerId: string, modelId: string, model?: any): 'free' | 'paid' | null {
		// 1. Check the model's own tier field (set by gateway from provider_model_tiers)
		if (model?.tier === 'free' || model?.tier === 'paid') {
			return model.tier;
		}
		// 2. Check if this backend model is used by any facade model
		for (const fm of facadeModels) {
			for (const b of (fm.backends || [])) {
				if (b.provider === providerId && (b.model === modelId || b.model === '*')) {
					return fm.tier || 'free';
				}
			}
		}
		return null; // not mapped to any facade model
	}

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
			base_url: 'https://api.z.ai/api/paas/v4',
			description: 'OpenAI-compatible provider at https://api.z.ai/api/paas/v4. Add multiple API keys — requests automatically fall back to the next key on failure.',
			docs_url: 'https://docs.z.ai/guides/overview/quick-start',
			icon: '☁'
		},
		zenmux: {
			name: 'ZenMux',
			base_url: 'https://zenmux.ai/api/v1',
			description: 'OpenAI-compatible multi-provider router. Add multiple API keys — requests automatically fall back to the next key on failure. Free models include deepseek-v4-flash-free and glm-4.7-flash-free.',
			docs_url: 'https://docs.zenmux.ai',
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
			const modelsRes = await gw('/admin/models');
			providerHealth = health.providers || {};
			facadeModels = modelsRes.models || [];

			// Load saved enabled models state
			let savedEnabled: Record<string, string[]> = {};
			try {
				const em = await gw('/admin/enabled-models');
				savedEnabled = em.enabled_models || {};
			} catch { /* first time — no saved state yet */ }

			providers = Object.entries(config.providers || {}).map(([id, p]: [string, any]) => {
				const tmpl = PROVIDER_TEMPLATES[id] || {};
				return {
					id,
					name: p.name || tmpl.name || id,
					base_url: p.base_url || tmpl.base_url || '',
					api_keys: p.api_keys || [],
					endpoints: p.endpoints || [],
					description: tmpl.description || '',
					docs_url: tmpl.docs_url || '',
					icon: tmpl.icon || '☁',
					health: providerHealth[id] || {},
					models: [], // populated by sync
					enabledModels: new Set(savedEnabled[id] || []),
				};
			});

			connected = true;
			hasUnsavedChanges = false;
			// Collapsed by default — admin expands a card when needed
			providers.forEach(p => { expandedProviders[p.id] = false; });
			// Auto-sync models for all providers that have base_url and keys
			for (const p of providers) {
				if (p.base_url && p.api_keys.length > 0) {
					syncModels(p).catch(() => {});
				}
			}
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
				endpoints: (p.endpoints || []).filter((e) => (e.account_id || e.base_url) && e.api_key),
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

	const PROVIDER_DOMAINS: Record<string, string> = {
		cloudflare: 'cloudflare.com',
		freemodel: 'freemodel.dev',
		llm7: 'llm7.io',
		zai: 'z.ai',
		freellmapi: 'codesai.cc'
	};

	function providerLogo(provider: any): string {
		let domain = PROVIDER_DOMAINS[provider.id] || '';
		if (!domain && provider.base_url) {
			try { domain = new URL(provider.base_url.replace('{account_id}', 'x')).hostname.replace(/^www\./, ''); } catch {}
		}
		if (!domain && provider.docs_url) {
			try { domain = new URL(provider.docs_url).hostname.replace(/^www\./, ''); } catch {}
		}
		return domain ? `https://www.google.com/s2/favicons?sz=64&domain=${domain}` : '';
	}

	function addEndpoint(provider: any) {
		if (!provider.endpoints) provider.endpoints = [];
		provider.endpoints = [
			...provider.endpoints,
			provider.id === 'cloudflare' ? { account_id: '', api_key: '' } : { base_url: '', api_key: '' }
		];
		providers = providers;
	}

	function removeEndpoint(provider: any, idx: number) {
		provider.endpoints = (provider.endpoints || []).filter((_: any, i: number) => i !== idx);
		providers = providers;
	}

	function addSingleAccount(provider: any) {
		if (!cfAccountId.trim() || !cfAccountKey.trim()) { toast.error('Enter account ID and API key'); return; }
		if (!provider.endpoints) provider.endpoints = [];
		const entry = provider.id === 'cloudflare'
			? { account_id: cfAccountId.trim(), api_key: cfAccountKey.trim() }
			: { base_url: cfAccountId.trim(), api_key: cfAccountKey.trim() };
		provider.endpoints = [...provider.endpoints, entry];
		providers = providers;
		cfAccountId = ''; cfAccountKey = '';
		toast.success('Account added — click Save Config');
	}

	function bulkAddAccounts(provider: any) {
		if (!bulkAccountsText.trim()) { toast.error('Paste accounts first'); return; }
		if (!provider.endpoints) provider.endpoints = [];
		const lines = bulkAccountsText.split('\n').map((l: string) => l.trim()).filter((l: string) => l && !l.startsWith('#'));
		const added: any[] = [];
		for (const line of lines) {
			const comma = line.indexOf(',');
			if (comma === -1) continue;
			const id = line.slice(0, comma).trim();
			const key = line.slice(comma + 1).trim();
			if (!id || !key) continue;
			added.push(provider.id === 'cloudflare' ? { account_id: id, api_key: key } : { base_url: id, api_key: key });
		}
		if (!added.length) { toast.error('No valid "id, apikey" lines found'); return; }
		provider.endpoints = [...provider.endpoints, ...added];
		providers = providers;
		bulkAccountsText = '';
		toast.success(`Added ${added.length} account(s) — click Save Config`);
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

	// Per-provider bulk key add (isolated textarea per provider card).
	async function addBulkKeys(provider: any) {
		const keys = (bulkByProvider[provider.id] || '')
			.split('\n').map(k => k.trim()).filter(k => k && !k.startsWith('#'));
		if (!keys.length) { toast.error('Paste API keys first'); return; }
		const allKeys = [...new Set([...provider.api_keys, ...keys])];
		try {
			await gw(`/admin/providers/${provider.id}`, 'PUT', {
				name: provider.name,
				base_url: provider.base_url,
				api_keys: allKeys,
			});
			toast.success(`Added ${keys.length} keys to ${provider.name}`);
			bulkByProvider[provider.id] = '';
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
				tier: m.tier || null,
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

	// ── Facade Model CRUD ────────────────────────────────────────────

	async function createFacadeModel() {
		if (!newFacadeModel.id || !newFacadeModel.name) {
			toast.error('Model ID and Display Name are required');
			return;
		}
		// Allow model="*" (all provider models) or a specific model
		const backends = newFacadeModel.backends.filter(b => b.provider && (b.model || b.model === '*'));
		if (!backends.length) {
			toast.error('Add at least one backend (provider + model)');
			return;
		}
		try {
			await gw('/admin/models', 'POST', {
				id: newFacadeModel.id,
				name: newFacadeModel.name,
				tier: newFacadeModel.tier,
				backends,
			});
			toast.success(`Facade model "${newFacadeModel.name}" created`);
			newFacadeModel = { id: '', name: '', tier: 'free', backends: [{ provider: '', model: '' }] };
			showAddFacadeModel = false;
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function updateFacadeModel(model: any) {
		try {
			await gw(`/admin/models/${model.id}`, 'PUT', {
				name: model.name,
				tier: model.tier,
				backends: model.backends,
			});
			toast.success(`"${model.name}" updated`);
			editingModel = null;
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function deleteFacadeModel(id: string, name: string) {
		if (!confirm(`Delete facade model "${name}"? Users will no longer see it.`)) return;
		try {
			await gw(`/admin/models/${id}`, 'DELETE');
			toast.success(`"${name}" deleted`);
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function toggleTier(model: any) {
		const newTier = model.tier === 'free' ? 'paid' : 'free';
		try {
			await gw(`/admin/models/${model.id}/tier`, 'POST', { tier: newTier });
			model.tier = newTier;
			facadeModels = facadeModels;
			toast.success(`"${model.name}" set to ${newTier.toUpperCase()}`);
		} catch (e: any) { toast.error(e.message); }
	}

	function addBackend(model: any) {
		model.backends = [...(model.backends || []), { provider: '', model: '' }];
		if (editingModel) editingModel = editingModel;
		else newFacadeModel = newFacadeModel;
	}

	function removeBackend(model: any, idx: number) {
		model.backends = model.backends.filter((_: any, i: number) => i !== idx);
		if (editingModel) editingModel = editingModel;
		else newFacadeModel = newFacadeModel;
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

	async function saveEnabledModels() {
		savingEnabled = true;
		try {
			const payload: Record<string, string[]> = {};
			for (const p of providers) {
				payload[p.id] = [...p.enabledModels];
			}
			await gw('/admin/enabled-models', 'PUT', { enabled_models: payload });
			hasUnsavedChanges = false;
			const total = Object.values(payload).reduce((a, b) => a + b.length, 0);
			toast.success(`Saved ${total} enabled models across ${providers.length} providers`);
		} catch (e: any) {
			toast.error(`Failed to save: ${e.message}`);
		}
		savingEnabled = false;
	}

	function markUnsaved() {
		hasUnsavedChanges = true;
		providers = providers; // trigger reactivity
	}

	onMount(() => { loadAll(); });
</script>

<!-- ══════════════════════════════════════════════════════════════════ -->

<div class="providers-shell flex flex-col h-full overflow-y-auto">
	<!-- Header -->
	<div class="px-4 sm:px-6 pt-4 pb-2">
		<div class="flex flex-wrap items-center justify-between gap-2">
			<div class="flex items-center gap-3">
				<h1 class="text-xl font-bold">Providers</h1>
				<span class="text-[11px] px-2 py-0.5 rounded-full font-medium {connected ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}">
					{connected ? '● connected' : '○ disconnected'}
				</span>
			</div>
			<div class="flex items-center gap-1.5">
				<button
					on:click={() => (showGatewayConfig = !showGatewayConfig)}
					class="text-xs px-2.5 py-1.5 rounded-lg text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition"
				>Gateway…</button>
				<button
					on:click={loadAll}
					class="text-xs px-2.5 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-700 transition"
				>↻ Refresh</button>
			</div>
		</div>
		<p class="text-xs text-gray-500 mt-0.5">Manage AI model providers, facade models, and tiers</p>

		<!-- Tabs -->
		<div class="flex gap-0.5 mt-3 border-b border-gray-200 dark:border-gray-800">
			<button
				class="px-3 py-2 text-sm font-medium -mb-px border-b-2 {activeTab === 'providers' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}"
				on:click={() => (activeTab = 'providers')}
			>Providers <span class="text-xs opacity-60">({providers.length})</span></button>
			<button
				class="px-3 py-2 text-sm font-medium -mb-px border-b-2 {activeTab === 'models' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}"
				on:click={() => (activeTab = 'models')}
			>Facade Models <span class="text-xs opacity-60">({facadeModels.length})</span></button>
		</div>
	</div>

	<!-- Gateway Config Banner -->
	{#if showGatewayConfig}
		<div class="mx-4 sm:mx-6 mb-3 bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800">
			<h3 class="text-sm font-semibold mb-3">Gateway Connection</h3>
			<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
				<div>
					<label class="text-xs text-gray-500 mb-1 block">Gateway URL</label>
					<input bind:value={GATEWAY_URL} placeholder="https://gateway…"
						class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-500 mb-1 block">Admin Key</label>
					<input type="password" bind:value={GATEWAY_ADMIN_KEY} placeholder="sk-gateway-admin"
						class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
				</div>
			</div>
			<button on:click={saveGatewayConfig}
				class="px-4 py-2 bg-blue-600 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-blue-700 transition">
				Connect
			</button>
		</div>
	{/if}

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
		</div>
	{:else if connected}

	{#if activeTab === 'providers'}
		<!-- Action bar -->
		<div class="flex items-center justify-between px-4 sm:px-6 pt-1 pb-2 gap-2">
			{#if hasUnsavedChanges}
				<button
					on:click={saveEnabledModels}
					disabled={savingEnabled}
					class="text-xs px-3 py-1.5 bg-green-700 text-gray-900 dark:text-white rounded-lg hover:bg-green-600 transition font-medium flex items-center gap-1.5 {savingEnabled ? 'opacity-50' : ''}"
				>
					{#if savingEnabled}
						<span class="animate-spin inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full"></span>
						Saving…
					{:else}
						💾 Save Model States
					{/if}
				</button>
			{:else}
				<span class="text-xs text-gray-500">All changes saved</span>
			{/if}
			<button
				on:click={() => (showAddProvider = true)}
				class="text-xs px-3 py-1.5 bg-blue-600 text-gray-900 dark:text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-1"
			>
				<span class="text-sm leading-none">+</span> Add Provider
			</button>
		</div>

		<!-- Add Provider Form -->
		{#if showAddProvider}
			<div class="mx-4 sm:mx-6 mb-3 bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800">
				<div class="flex flex-wrap items-center justify-between mb-3 gap-2">
					<h3 class="text-sm font-semibold">Add New Provider</h3>
					<div class="flex flex-wrap gap-1">
						{#each Object.entries(PROVIDER_TEMPLATES) as [tid, tmpl]}
							<button on:click={() => applyTemplate(tid)}
								class="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-700 transition">
								{tmpl.name}
							</button>
						{/each}
					</div>
				</div>
				<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
					<div>
						<label class="text-xs text-gray-500 mb-1 block">Provider ID</label>
						<input bind:value={newProvider.id} placeholder="e.g. freemodel"
							class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
					</div>
					<div>
						<label class="text-xs text-gray-500 mb-1 block">Display Name</label>
						<input bind:value={newProvider.name} placeholder="e.g. FreeModel.dev"
							class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
					</div>
					<div>
						<label class="text-xs text-gray-500 mb-1 block">Base URL</label>
						<input bind:value={newProvider.base_url} placeholder="https://api.provider.com/v1"
							class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
					</div>
				</div>
				<div class="mb-3">
					<label class="text-xs text-gray-500 mb-1 block">API Keys (one per line)</label>
					<textarea
						bind:value={newProvider.api_keys[0]}
						placeholder="sk-key-1"
						rows="2"
						class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm font-mono"
					></textarea>
				</div>
				<div class="flex gap-2">
					<button on:click={createProvider} class="px-4 py-2 bg-blue-600 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-blue-700 transition">Create</button>
					<button on:click={() => (showAddProvider = false)} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
				</div>
			</div>
		{/if}

		<!-- ══ PROVIDERS LIST ══ -->
		<div class="flex flex-col gap-3 px-4 sm:px-6 pb-6">
			{#each providers as provider (provider.id)}
				{@const health = provider.health || {}}
				{@const freeCount = (provider.models || []).filter(m => getModelTier(provider.id, m.id, m) === 'free').length}
				<div class="provider-card rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden bg-white dark:bg-gray-900/60 {health.in_cooldown ? 'border-l-4 border-l-red-500' : health.failures > 0 ? 'border-l-4 border-l-amber-500' : 'border-l-4 border-l-green-500'}">

					<!-- Provider header -->
					<button
						class="w-full flex items-center gap-3 px-3.5 py-2.5 hover:bg-gray-100 dark:hover:bg-gray-800/50 transition cursor-pointer text-left"
						on:click={() => { expandedProviders[provider.id] = !expandedProviders[provider.id]; }}
					>
						<img src={providerLogo(provider) || '/favicon.png'} alt="" class="size-5 rounded object-contain bg-white/5 shrink-0" on:error={(e) => { e.currentTarget.src = '/favicon.png'; }} />
						<div class="flex-1 min-w-0">
							<div class="flex items-center gap-2 flex-wrap">
								<h2 class="font-semibold text-sm truncate">{provider.name}</h2>
								{#if health.in_cooldown}
									<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-red-900/40 text-red-400">COOLDOWN</span>
								{:else if health.failures > 0}
									<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-900/40 text-amber-400">{health.failures} FAIL</span>
								{:else}
									<span class="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-green-900/40 text-green-400">OK</span>
								{/if}
							</div>
							<div class="text-[11px] text-gray-500 font-mono truncate">{provider.base_url || 'Not configured'}</div>
						</div>
						<div class="flex items-center gap-1.5 shrink-0 text-[11px] text-gray-500">
							<span class="px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800">{provider.api_keys.length} 🔑</span>
							<span class="hidden sm:inline px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800">{(provider.models || []).length} models</span>
							{#if freeCount > 0}
								<span class="px-2 py-0.5 rounded-full bg-green-500/10 text-green-400">{freeCount} free</span>
							{/if}
							<svg class="w-4 h-4 text-gray-500 transition-transform {expandedProviders[provider.id] ? 'rotate-180' : ''}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
								<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z" clip-rule="evenodd" />
							</svg>
						</div>
					</button>

					{#if expandedProviders[provider.id]}
						<div class="border-t border-gray-200 dark:border-gray-800 grid grid-cols-1 lg:grid-cols-2" transition:slide={{ duration: 200 }}>

							<!-- ══ CONFIG ══ -->
							<div class="p-3.5 space-y-3 bg-white dark:bg-gray-900/80">
								{#if PROVIDER_TEMPLATES[provider.id]?.description}
									<p class="text-[11px] text-gray-500 leading-relaxed">
										{PROVIDER_TEMPLATES[provider.id].description}
										{#if PROVIDER_TEMPLATES[provider.id]?.docs_url}
											<a href={PROVIDER_TEMPLATES[provider.id].docs_url} target="_blank" class="text-blue-400 hover:text-blue-300">Docs →</a>
										{/if}
									</p>
								{/if}

								<!-- Base URL -->
								<div>
									<label class="text-[11px] font-medium text-gray-500 block mb-1">Base URL</label>
									<input bind:value={provider.base_url}
										class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono" />
								</div>

								<!-- Bulk keys -->
								<div>
									<label class="text-[11px] font-medium text-gray-500 block mb-1">API keys — paste one per line</label>
									<div class="flex flex-col gap-1.5">
										<textarea
											placeholder="sk-key-1&#10;sk-key-2&#10;sk-key-3"
											rows="2"
											bind:value={bulkByProvider[provider.id]}
											class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-2.5 py-1.5 text-xs font-mono"
										></textarea>
										<div class="flex flex-wrap gap-1.5">
											<button on:click={() => addBulkKeys(provider)}
												class="px-2.5 py-1.5 bg-blue-600 text-gray-900 dark:text-white text-xs rounded-lg hover:bg-blue-700 transition">+ Add Keys</button>
											<button on:click={() => syncModels(provider)}
												class="px-2.5 py-1.5 bg-gray-700 text-xs rounded-lg hover:bg-gray-600 transition">↻ Sync Models</button>
										</div>
									</div>
								</div>

								<!-- Key list -->
								{#if provider.api_keys.length > 0}
									<div class="space-y-1">
										<label class="text-[11px] font-medium text-gray-500 block">Configured keys ({provider.api_keys.length})</label>
										{#each provider.api_keys as key, i}
											<div class="flex items-center gap-2 bg-gray-100 dark:bg-gray-800/70 rounded-lg px-2 py-1.5 border border-gray-200 dark:border-gray-700/50">
												<span class="text-[11px] text-gray-400 font-mono flex-1 truncate">{maskKey(key)}</span>
												<button class="text-[11px] px-1.5 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition"
													on:click={async () => {
														try {
															const res = await gw(`/admin/providers/${provider.id}/models`);
															const count = (res.data || res.models || []).length;
															toast.success(`Key #${i + 1} works — ${count} models`);
														} catch (e) { toast.error(`Key #${i + 1} test failed: ${e.message}`); }
													}}>Test</button>
												<button class="text-red-500 hover:text-red-400 transition"
													on:click={() => { removeKey(provider, i); saveProvider(provider); }}>
													<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" /></svg>
												</button>
											</div>
										{/each}
									</div>
								{/if}

								<!-- Extra accounts -->
								<div class="border-t border-gray-200 dark:border-gray-700/40 pt-2.5">
									<div class="flex items-center justify-between mb-1">
										<label class="text-[11px] font-medium text-gray-500">{provider.id === 'cloudflare' ? 'Cloudflare accounts (ID + token)' : 'Extra accounts (URL + key)'}</label>
										<button on:click={() => addEndpoint(provider)} class="text-[11px] px-2 py-0.5 bg-gray-700 rounded hover:bg-gray-600 transition">+ Add</button>
									</div>
									<p class="text-[10px] text-gray-500 mb-1.5">Rotates past per-account quota (429/402).</p>
									<div class="flex flex-col gap-1.5">
										<textarea bind:value={bulkAccountsText} rows="2" placeholder="Bulk — one per line:  accountid, apikey"
											class="w-full text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1.5 font-mono outline-none"></textarea>
										<button on:click={() => bulkAddAccounts(provider)} class="text-[11px] px-2.5 py-1 bg-gray-700 rounded-lg hover:bg-gray-600 transition self-start">Bulk add</button>
									</div>
									{#if (provider.endpoints || []).length > 0}
										<div class="flex flex-col gap-1.5 mt-1.5">
											{#each provider.endpoints as ep, i}
												<div class="flex flex-col sm:flex-row sm:items-center gap-1.5">
													{#if provider.id === 'cloudflare'}
														<input bind:value={ep.account_id} placeholder="Account ID" class="flex-1 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 font-mono outline-none" />
													{:else}
														<input bind:value={ep.base_url} placeholder="Base URL" class="flex-1 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 font-mono outline-none" />
													{/if}
													<input bind:value={ep.api_key} placeholder="API token" type="password" class="flex-1 text-xs bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 font-mono outline-none" />
													<button class="text-red-500 hover:text-red-400 transition" on:click={() => removeEndpoint(provider, i)} aria-label="Remove account">
														<svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd" /></svg>
													</button>
												</div>
											{/each}
										</div>
									{/if}
								</div>

								<!-- Actions -->
								<div class="flex flex-wrap items-center justify-between gap-2 pt-0.5">
									<div class="flex gap-1.5">
										<button on:click={() => saveProvider(provider)} class="px-2.5 py-1.5 bg-green-700 text-gray-900 dark:text-white text-xs rounded-lg hover:bg-green-600 transition">Save Config</button>
										<button on:click={() => resetProvider(provider.id)} class="px-2.5 py-1.5 bg-gray-700 text-xs rounded-lg hover:bg-gray-600 transition">Reset Health</button>
									</div>
									<button on:click={() => deleteProvider(provider.id, provider.name)} class="text-xs text-red-400 hover:text-red-300 transition">Delete</button>
								</div>
							</div>

							<!-- ══ MODELS ══ -->
							<div class="border-t lg:border-t-0 lg:border-l border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900/40">
								{#if provider.models && provider.models.length > 0}
									<div class="p-3.5 space-y-2">
										<div class="flex flex-wrap items-center gap-1.5">
											<div class="relative flex-1 min-w-[140px]">
												<input bind:value={providerSearch[provider.id]} placeholder="Search models…"
													class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 pl-7 pr-2.5 py-1.5 text-xs" />
												<svg class="absolute left-2 top-2 w-3 h-3 text-gray-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" /></svg>
											</div>
											<button on:click={() => { const q = (providerSearch[provider.id] || '').toLowerCase(); const filtered = provider.models.filter(m => !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q)); filtered.forEach(m => provider.enabledModels.add(m.id)); markUnsaved(); toast.success(`Enabled ${filtered.length} models`); }}
												class="text-[11px] px-2 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition">Enable All</button>
											<button on:click={() => { const q = (providerSearch[provider.id] || '').toLowerCase(); const filtered = provider.models.filter(m => !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q)); filtered.forEach(m => provider.enabledModels.delete(m.id)); markUnsaved(); toast.success(`Disabled ${filtered.length} models`); }}
												class="text-[11px] px-2 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition">Disable All</button>
											<button on:click={() => syncModels(provider)} class="text-[11px] px-2 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition" title="Refresh models">↻</button>
										</div>
										<div class="text-[11px] text-gray-500 flex items-center justify-between">
											<span>{provider.models.length} models · {provider.enabledModels.size} enabled</span>
											{#if hasUnsavedChanges}
												<button on:click={saveEnabledModels} disabled={savingEnabled}
													class="text-[11px] px-2 py-1 bg-green-700 text-gray-900 dark:text-white rounded-lg hover:bg-green-600 transition {savingEnabled ? 'opacity-50' : ''}">💾 Save</button>
											{/if}
										</div>
										<div class="divide-y divide-gray-200 dark:divide-gray-800/60 max-h-80 overflow-y-auto pr-0.5">
											{#each provider.models.filter(m => { const q = (providerSearch[provider.id] || '').toLowerCase(); return !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q); }) as model}
												{@const tier = getModelTier(provider.id, model.id, model)}
												<div class="py-2 flex items-center gap-2 hover:bg-gray-100 dark:hover:bg-gray-800/40 transition px-1 rounded-md">
													<div class="flex-1 min-w-0">
														<div class="text-[13px] font-medium truncate leading-tight">{model.name}</div>
														<div class="text-[11px] text-blue-400 font-mono truncate leading-tight">{model.id}</div>
													</div>
													<div class="flex items-center gap-1 flex-shrink-0">
														{#if tier === 'free'}
															<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-green-500/20 text-green-400">FREE</span>
														{:else if tier === 'paid'}
															<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/20 text-amber-400">PAID</span>
														{:else}
															<span class="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-gray-500/20 text-gray-400">—</span>
														{/if}
														{#if model.context_length}
															<span class="hidden md:inline text-[9px] px-1.5 py-0.5 rounded-full bg-gray-700 text-gray-300">
																{model.context_length >= 1000000 ? `${(model.context_length / 1000000).toFixed(1)}M` : model.context_length >= 1000 ? `${Math.round(model.context_length / 1000)}K` : model.context_length}
															</span>
														{/if}
														<button class="w-9 h-5 rounded-full transition relative flex-shrink-0 {provider.enabledModels.has(model.id) ? 'bg-blue-500' : 'bg-gray-600'}"
															on:click={() => { if (provider.enabledModels.has(model.id)) { provider.enabledModels.delete(model.id); } else { provider.enabledModels.add(model.id); } markUnsaved(); }}>
															<span class="absolute top-0.5 {provider.enabledModels.has(model.id) ? 'right-0.5' : 'left-0.5'} w-4 h-4 rounded-full bg-white transition-all shadow"></span>
														</button>
													</div>
												</div>
											{/each}
										</div>
									</div>
								{:else}
									<div class="p-4 text-center">
										<p class="text-xs text-gray-500 mb-2">No models loaded.</p>
										<button on:click={() => syncModels(provider)} class="text-xs px-2.5 py-1.5 bg-blue-600 text-gray-900 dark:text-white rounded-lg hover:bg-blue-700 transition">↻ Sync Models</button>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			{/each}

			{#if providers.length === 0}
				<div class="text-center py-16">
					<p class="text-gray-600 dark:text-gray-400 mb-2">No providers configured yet.</p>
					<button on:click={() => (showAddProvider = true)}
						class="px-4 py-2 bg-blue-600 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-blue-700 transition">
						+ Add Your First Provider
					</button>
				</div>
			{/if}
		</div>

	{:else if activeTab === 'models'}
		<!-- ══ FACADE MODELS ══ -->
		<div class="flex flex-col gap-3 px-4 sm:px-6 pb-6 pt-1">
			<div class="flex justify-end">
				<button
					on:click={() => { showAddFacadeModel = true; editingModel = null; }}
					class="text-xs px-3 py-1.5 bg-blue-600 text-gray-900 dark:text-white rounded-lg hover:bg-blue-700 transition flex items-center gap-1"
				>
					<span class="text-sm leading-none">+</span> Add Facade Model
				</button>
			</div>

			{#if showAddFacadeModel || editingModel}
				{@const isEdit = !!editingModel}
				{@const fm = editingModel || newFacadeModel}
				<div class="bg-white dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-800">
					<h3 class="text-sm font-semibold mb-3">{isEdit ? `Edit: ${fm.name}` : 'Create Facade Model'}</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
						<div>
							<label class="text-xs text-gray-500 mb-1 block">Model ID</label>
							<input bind:value={fm.id} placeholder="e.g. claude-opus-4.8" disabled={isEdit}
								class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm font-mono {isEdit ? 'opacity-50' : ''}" />
						</div>
						<div>
							<label class="text-xs text-gray-500 mb-1 block">Display Name (shown to users)</label>
							<input bind:value={fm.name} placeholder="e.g. Claude Opus 4.8"
								class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
						</div>
						<div>
							<label class="text-xs text-gray-500 mb-1 block">Tier</label>
							<select bind:value={fm.tier}
								class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm">
								<option value="free">FREE</option>
								<option value="paid">PAID</option>
							</select>
						</div>
					</div>
					<div class="mb-3">
						<label class="text-xs text-gray-500 mb-2 block">Backends (fallback order — first provider tried first)</label>
						{#each fm.backends as backend, i}
							<div class="flex flex-wrap gap-2 mb-2 items-center">
								<span class="text-xs text-gray-500 w-5 flex-shrink-0">{i + 1}.</span>
								<select bind:value={backend.provider}
									on:change={() => { backend.model = ''; }}
									class="flex-1 min-w-[140px] rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm">
									<option value="">Select provider…</option>
									{#each providers as p}<option value={p.id}>{p.name}</option>{/each}
								</select>
								<select bind:value={backend.model}
									class="flex-1 min-w-[140px] rounded-lg border border-gray-600 bg-white dark:bg-gray-900 px-3 py-2 text-sm font-mono">
									<option value="">Select model…</option>
									<option value="*">★ All models (auto-fallback)</option>
									{#if backend.provider}
										{@const prov = providers.find(p => p.id === backend.provider)}
										{#if prov?.models?.length}{#each prov.models as m}<option value={m.id}>{m.name || m.id}</option>{/each}{/if}
									{/if}
								</select>
								<button on:click={() => removeBackend(fm, i)} class="text-red-500 hover:text-red-400 text-sm px-2 py-1 flex-shrink-0">✕</button>
							</div>
						{/each}
						<button on:click={() => addBackend(fm)} class="text-xs text-blue-400 hover:text-blue-300 transition mt-1">+ Add fallback backend</button>
					</div>
					<div class="flex gap-2">
						{#if isEdit}
							<button on:click={() => updateFacadeModel(fm)} class="px-4 py-2 bg-green-700 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-green-600 transition">Save Changes</button>
							<button on:click={() => (editingModel = null)} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
						{:else}
							<button on:click={createFacadeModel} class="px-4 py-2 bg-blue-600 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-blue-700 transition">Create</button>
							<button on:click={() => (showAddFacadeModel = false)} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
						{/if}
					</div>
				</div>
			{/if}

			{#if facadeModels.length > 0}
				<div class="relative">
					<input bind:value={modelSearchQuery} placeholder="Search facade models…"
						class="w-full rounded-lg border border-gray-600 bg-white dark:bg-gray-900 pl-8 pr-3 py-2 text-sm" />
					<svg class="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-gray-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" /></svg>
				</div>
			{/if}

			{#each facadeModels.filter(m => !modelSearchQuery || m.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) || m.id.toLowerCase().includes(modelSearchQuery.toLowerCase())) as model (model.id)}
				<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
					<div class="px-4 py-2.5 flex items-center justify-between gap-2">
						<div class="min-w-0">
							<div class="font-semibold text-sm truncate">{model.name}</div>
							<span class="text-[11px] text-gray-500 font-mono">{model.id}</span>
						</div>
						<div class="flex items-center gap-2 flex-shrink-0">
							<button on:click={() => toggleTier(model)}
								class="text-[11px] font-bold px-2.5 py-1 rounded-full transition cursor-pointer {model.tier === 'free' ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-amber-500/20 text-amber-400 hover:bg-amber-500/30'}">
								{model.tier === 'free' ? 'FREE' : 'PAID'}
							</button>
							<span class="text-[11px] text-gray-500 hidden sm:inline">{(model.backends || []).length} backend{(model.backends || []).length !== 1 ? 's' : ''}</span>
							<button on:click={() => { editingModel = JSON.parse(JSON.stringify(model)); showAddFacadeModel = false; }}
								class="text-[11px] px-2 py-1 bg-gray-700 rounded hover:bg-gray-600 transition">Edit</button>
							<button on:click={() => deleteFacadeModel(model.id, model.name)} class="text-red-500 hover:text-red-400 transition">
								<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.519.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clip-rule="evenodd" /></svg>
							</button>
						</div>
					</div>
					{#if model.backends && model.backends.length > 0}
						<div class="border-t border-gray-200 dark:border-gray-800 px-4 py-2 bg-white dark:bg-gray-900/30">
							<div class="flex flex-wrap gap-1.5">
								{#each model.backends as b, i}
									<span class="text-[11px] px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 font-mono">
										{i + 1}. {b.provider} → {b.model === '*' ? '★' : b.model}
									</span>
								{/each}
							</div>
						</div>
					{/if}
				</div>
			{/each}

			{#if facadeModels.length === 0}
				<div class="text-center py-16">
					<p class="text-gray-600 dark:text-gray-400 mb-2">No facade models configured yet.</p>
					<p class="text-xs text-gray-500 mb-4">Facade models are what users see. Each maps to one or more provider backends for fallback.</p>
					<button on:click={() => (showAddFacadeModel = true)}
						class="px-4 py-2 bg-blue-600 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-blue-700 transition">
						+ Create Your First Facade Model
					</button>
				</div>
			{/if}
		</div>
	{/if}

	{/if}
</div>

<style>
	/* Match the chat input box: #292929 surface, faint border, xl radius */
	input:not([type='checkbox']):not([type='radio']),
	textarea,
	select {
		background-color: #292929 !important;
		border-color: #ffffff1a !important;
		border-radius: var(--radius-xl) !important;
	}
	.provider-card {
		transition: border-color 0.15s ease;
	}
</style>
