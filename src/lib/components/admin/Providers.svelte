<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { config } from '$lib/stores';
	import Tooltip from '$lib/components/common/Tooltip.svelte';

	const i18n = getContext('i18n');

	// Gateway URL — set in admin settings or env
	let GATEWAY_URL = localStorage.getItem('gateway_url') || '';
	let GATEWAY_ADMIN_KEY = localStorage.getItem('gateway_admin_key') || '';

	let providers: any[] = [];
	let facadeModels: any[] = [];
	let providerHealth: any = {};

	let showGatewayConfig = false;
	let showAddProvider = false;
	let showAddModel = false;
	let showBulkUpload = false;
	let editingProvider: any = null;
	let editingModel: any = null;

	// New provider form
	let newProvider = { id: '', name: '', base_url: '', api_keys: [''], tier: 'free' };

	// New model form
	let newModel = { id: '', name: '', tier: 'paid', backends: [{ provider: '', model: '' }] };

	// Bulk upload
	let bulkText = '';

	// ── Gateway API helpers ────────────────────────────────────────────

	async function gatewayFetch(path: string, method = 'GET', body?: any) {
		const url = `${GATEWAY_URL}${path}`;
		const opts: any = {
			method,
			headers: {
				'Content-Type': 'application/json',
				'Authorization': `Bearer ${GATEWAY_ADMIN_KEY}`
			}
		};
		if (body) opts.body = JSON.stringify(body);
		const res = await fetch(url, opts);
		if (!res.ok) {
			const err = await res.text();
			throw new Error(err);
		}
		return res.json();
	}

	// ── Load data ──────────────────────────────────────────────────────

	async function loadProviders() {
		try {
			const res = await gatewayFetch('/admin/providers');
			providerHealth = res.providers || {};

			// Also load full provider config
			const configRes = await gatewayFetch('/admin/config');
			providers = Object.entries(configRes.providers || {}).map(([id, p]: [string, any]) => ({
				id,
				...p,
				api_keys: p.api_keys || [p.api_key || ''],
			}));
		} catch (e) {
			// Providers endpoint might not have full config yet
			try {
				const res = await gatewayFetch('/admin/providers');
				providerHealth = res.providers || {};
				providers = Object.entries(providerHealth).map(([id, p]: [string, any]) => ({
					id,
					name: p.name,
					base_url: p.base_url,
					api_keys: [],
					failures: p.failures,
					in_cooldown: p.in_cooldown,
				}));
			} catch (e2) {
				console.error('Failed to load providers', e2);
			}
		}
	}

	async function loadModels() {
		try {
			const res = await gatewayFetch('/admin/models');
			facadeModels = res.models || [];
		} catch (e) {
			console.error('Failed to load models', e);
		}
	}

	async function loadAll() {
		if (!GATEWAY_URL || !GATEWAY_ADMIN_KEY) {
			showGatewayConfig = true;
			return;
		}
		await Promise.all([loadProviders(), loadModels()]);
	}

	// ── Provider CRUD ──────────────────────────────────────────────────

	async function saveProvider(provider: any) {
		try {
			await gatewayFetch(`/admin/providers/${provider.id}`, 'PUT', {
				name: provider.name,
				base_url: provider.base_url,
				api_keys: provider.api_keys.filter((k: string) => k.trim()),
			});
			toast.success(`Provider "${provider.name}" updated`);
			await loadProviders();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function createProvider() {
		try {
			await gatewayFetch('/admin/providers', 'POST', {
				id: newProvider.id,
				name: newProvider.name,
				base_url: newProvider.base_url,
				api_keys: newProvider.api_keys.filter((k: string) => k.trim()),
			});
			toast.success(`Provider "${newProvider.name}" created`);
			newProvider = { id: '', name: '', base_url: '', api_keys: [''], tier: 'free' };
			showAddProvider = false;
			await loadProviders();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function deleteProvider(id: string) {
		if (!confirm('Delete this provider? Models using it will lose this backend.')) return;
		try {
			await gatewayFetch(`/admin/providers/${id}`, 'DELETE');
			toast.success('Provider deleted');
			await loadProviders();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function resetProvider(id: string) {
		try {
			await gatewayFetch(`/admin/providers/${id}/reset`, 'POST');
			toast.success('Provider reset');
			await loadProviders();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	// ── Bulk upload keys ───────────────────────────────────────────────

	async function bulkUploadKeys(providerId: string) {
		const keys = bulkText
			.split('\n')
			.map((k: string) => k.trim())
			.filter((k: string) => k && !k.startsWith('#'));

		if (!keys.length) {
			toast.error('No valid keys found');
			return;
		}

		const provider = providers.find((p: any) => p.id === providerId);
		if (!provider) return;

		const existingKeys = provider.api_keys || [];
		const allKeys = [...new Set([...existingKeys, ...keys])]; // deduplicate

		try {
			await gatewayFetch(`/admin/providers/${providerId}`, 'PUT', {
				name: provider.name,
				base_url: provider.base_url,
				api_keys: allKeys,
			});
			toast.success(`Added ${keys.length} keys to ${provider.name}`);
			bulkText = '';
			showBulkUpload = false;
			await loadProviders();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	// ── Model CRUD ─────────────────────────────────────────────────────

	async function createModel() {
		try {
			await gatewayFetch('/admin/models', 'POST', newModel);
			toast.success(`Model "${newModel.name}" created`);
			newModel = { id: '', name: '', tier: 'paid', backends: [{ provider: '', model: '' }] };
			showAddModel = false;
			await loadModels();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function updateModel(model: any) {
		try {
			await gatewayFetch(`/admin/models/${model.id}`, 'PUT', {
				name: model.name,
				tier: model.tier,
				backends: model.backends,
			});
			toast.success(`Model "${model.name}" updated`);
			editingModel = null;
			await loadModels();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function deleteModel(id: string) {
		if (!confirm('Delete this facade model?')) return;
		try {
			await gatewayFetch(`/admin/models/${id}`, 'DELETE');
			toast.success('Model deleted');
			await loadModels();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	async function toggleModelTier(model: any) {
		const newTier = model.tier === 'free' ? 'paid' : 'free';
		try {
			await gatewayFetch(`/admin/models/${model.id}/tier`, 'POST', { tier: newTier });
			toast.success(`${model.name} → ${newTier.toUpperCase()}`);
			await loadModels();
		} catch (e: any) {
			toast.error(`Failed: ${e.message}`);
		}
	}

	// ── Gateway config ─────────────────────────────────────────────────

	function saveGatewayConfig() {
		localStorage.setItem('gateway_url', GATEWAY_URL);
		localStorage.setItem('gateway_admin_key', GATEWAY_ADMIN_KEY);
		showGatewayConfig = false;
		toast.success('Gateway config saved');
		loadAll();
	}

	// ── Key helpers ────────────────────────────────────────────────────

	function addKeyToProvider(provider: any) {
		provider.api_keys = [...provider.api_keys, ''];
		providers = providers;
	}

	function removeKeyFromProvider(provider: any, index: number) {
		provider.api_keys = provider.api_keys.filter((_: any, i: number) => i !== index);
		providers = providers;
	}

	function maskKey(key: string): string {
		if (!key || key.length < 8) return '••••••••';
		return key.slice(0, 4) + '••••' + key.slice(-4);
	}

	onMount(() => {
		loadAll();
	});

	let activeTab = 'providers';
	let bulkUploadProviderId = '';
</script>

<div class="flex flex-col gap-4 px-6 py-4 h-full overflow-y-auto">
	<!-- Gateway Connection Banner -->
	{#if showGatewayConfig || !GATEWAY_URL}
		<div class="bg-gray-50 dark:bg-gray-900 rounded-xl p-6 border border-gray-200 dark:border-gray-800">
			<h3 class="text-lg font-semibold mb-3">Gateway Connection</h3>
			<p class="text-sm text-gray-500 mb-4">Connect to your Facade Model Gateway to manage providers and models.</p>
			<div class="flex flex-col gap-3">
				<div>
					<label class="text-sm font-medium mb-1 block">Gateway URL</label>
					<input
						type="text"
						bind:value={GATEWAY_URL}
						placeholder="https://your-gateway.up.railway.app"
						class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
					/>
				</div>
				<div>
					<label class="text-sm font-medium mb-1 block">Admin API Key</label>
					<input
						type="password"
						bind:value={GATEWAY_ADMIN_KEY}
						placeholder="sk-gateway-admin"
						class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
					/>
				</div>
				<button
					on:click={saveGatewayConfig}
					class="self-start px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition"
				>
					Connect
				</button>
			</div>
		</div>
	{/if}

	{#if GATEWAY_URL && GATEWAY_ADMIN_KEY}
		<!-- Tabs -->
		<div class="flex gap-2 border-b border-gray-200 dark:border-gray-800">
			<button
				class="px-4 py-2 text-sm font-medium transition {activeTab === 'providers'
					? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
					: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
				on:click={() => (activeTab = 'providers')}
			>
				Providers
			</button>
			<button
				class="px-4 py-2 text-sm font-medium transition {activeTab === 'models'
					? 'border-b-2 border-blue-500 text-blue-600 dark:text-blue-400'
					: 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}"
				on:click={() => (activeTab = 'models')}
			>
				Facade Models
			</button>
			<div class="ml-auto flex items-center gap-2">
				<button
					on:click={() => (showGatewayConfig = !showGatewayConfig)}
					class="text-xs text-gray-400 hover:text-gray-600 transition"
				>
					Gateway Settings
				</button>
				<button
					on:click={loadAll}
					class="text-xs px-3 py-1 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition"
				>
					Refresh
				</button>
			</div>
		</div>

		<!-- PROVIDERS TAB -->
		{#if activeTab === 'providers'}
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-semibold">LLM Providers</h2>
				<button
					on:click={() => (showAddProvider = true)}
					class="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
						<path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
					</svg>
					Add Provider
				</button>
			</div>

			<!-- Add Provider Form -->
			{#if showAddProvider}
				<div class="bg-gray-50 dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
					<h3 class="text-sm font-semibold mb-3">New Provider</h3>
					<div class="grid grid-cols-2 gap-3 mb-3">
						<div>
							<label class="text-xs font-medium mb-1 block">Provider ID</label>
							<input
								bind:value={newProvider.id}
								placeholder="e.g. freemodel"
								class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
							/>
						</div>
						<div>
							<label class="text-xs font-medium mb-1 block">Display Name</label>
							<input
								bind:value={newProvider.name}
								placeholder="e.g. FreeModel.dev"
								class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
							/>
						</div>
					</div>
					<div class="mb-3">
						<label class="text-xs font-medium mb-1 block">Base URL</label>
						<input
							bind:value={newProvider.base_url}
							placeholder="https://api.freemodel.dev/v1"
							class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
						/>
					</div>
					<div class="mb-3">
						<label class="text-xs font-medium mb-1 block">API Keys</label>
						{#each newProvider.api_keys as key, i}
							<div class="flex gap-2 mb-1">
								<input
									bind:value={newProvider.api_keys[i]}
									placeholder="sk-..."
									type="password"
									class="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
								/>
								{#if newProvider.api_keys.length > 1}
									<button
										on:click={() => { newProvider.api_keys = newProvider.api_keys.filter((_, idx) => idx !== i); }}
										class="text-red-500 hover:text-red-700 text-sm px-2"
									>X</button>
								{/if}
							</div>
						{/each}
						<button
							on:click={() => { newProvider.api_keys = [...newProvider.api_keys, '']; }}
							class="text-xs text-blue-500 hover:text-blue-700 mt-1"
						>+ Add another key</button>
					</div>
					<div class="flex gap-2">
						<button on:click={createProvider} class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition">Create</button>
						<button on:click={() => (showAddProvider = false)} class="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-300 dark:hover:bg-gray-700 transition">Cancel</button>
					</div>
				</div>
			{/if}

			<!-- Provider List -->
			<div class="flex flex-col gap-3">
				{#each providers as provider}
					<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
						<div class="flex items-center justify-between mb-3">
							<div class="flex items-center gap-3">
								<h3 class="font-semibold">{provider.name || provider.id}</h3>
								<span class="text-xs text-gray-400">{provider.id}</span>

								<!-- Health indicator -->
								{#if providerHealth[provider.id]}
									{#if providerHealth[provider.id].in_cooldown}
										<span class="text-xs px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400">
											Cooldown ({providerHealth[provider.id].cooldown_remaining_s}s)
										</span>
									{:else if providerHealth[provider.id].failures > 0}
										<span class="text-xs px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400">
											{providerHealth[provider.id].failures} failures
										</span>
									{:else}
										<span class="text-xs px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400">
											Healthy
										</span>
									{/if}
								{/if}
							</div>

							<div class="flex items-center gap-2">
								<button
									on:click={() => resetProvider(provider.id)}
									class="text-xs px-2 py-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition"
								>Reset</button>
								<button
									on:click={() => { bulkUploadProviderId = provider.id; showBulkUpload = true; }}
									class="text-xs px-2 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-lg hover:bg-purple-200 dark:hover:bg-purple-900/50 transition"
								>Bulk Upload Keys</button>
								<button
									on:click={() => deleteProvider(provider.id)}
									class="text-xs px-2 py-1 text-red-500 hover:text-red-700 transition"
								>Delete</button>
							</div>
						</div>

						<div class="text-sm text-gray-500 mb-3">
							<span class="font-mono text-xs bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded">{provider.base_url || 'Not set'}</span>
						</div>

						<!-- API Keys -->
						<div>
							<div class="flex items-center justify-between mb-2">
								<label class="text-xs font-medium text-gray-600 dark:text-gray-400">
									API Keys ({(provider.api_keys || []).length})
								</label>
								<button
									on:click={() => addKeyToProvider(provider)}
									class="text-xs text-blue-500 hover:text-blue-700"
								>+ Add Key</button>
							</div>

							{#each provider.api_keys || [] as key, i}
								<div class="flex items-center gap-2 mb-1">
									<div class="flex-1 flex items-center gap-2">
										<span class="text-xs text-gray-400 w-6">#{i + 1}</span>
										<input
											type="password"
											bind:value={provider.api_keys[i]}
											class="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5 text-sm font-mono"
										/>
									</div>
									<button
										on:click={() => removeKeyFromProvider(provider, i)}
										class="text-red-400 hover:text-red-600 text-xs px-1"
									>X</button>
								</div>
							{/each}

							{#if (provider.api_keys || []).length > 0}
								<div class="mt-2 flex justify-end">
									<button
										on:click={() => saveProvider(provider)}
										class="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
									>Save Keys</button>
								</div>
							{/if}
						</div>
					</div>
				{/each}

				{#if providers.length === 0}
					<div class="text-center py-8 text-gray-400">
						No providers configured. Click "Add Provider" to get started.
					</div>
				{/if}
			</div>

			<!-- Bulk Upload Modal -->
			{#if showBulkUpload}
				<div class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
					<div class="bg-white dark:bg-gray-900 rounded-xl p-6 w-[500px] max-w-[90vw] border border-gray-200 dark:border-gray-800">
						<h3 class="text-lg font-semibold mb-2">Bulk Upload API Keys</h3>
						<p class="text-sm text-gray-500 mb-4">
							Paste one key per line. Duplicates will be skipped. Lines starting with # are ignored.
						</p>
						<textarea
							bind:value={bulkText}
							placeholder="sk-key-1&#10;sk-key-2&#10;sk-key-3&#10;# comment lines are ignored"
							rows="8"
							class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-2 text-sm font-mono mb-4"
						></textarea>
						<div class="flex justify-end gap-2">
							<button
								on:click={() => { showBulkUpload = false; bulkText = ''; }}
								class="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-300 dark:hover:bg-gray-700 transition"
							>Cancel</button>
							<button
								on:click={() => bulkUploadKeys(bulkUploadProviderId)}
								class="px-4 py-2 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 transition"
							>Upload {bulkText.split('\n').filter(l => l.trim() && !l.startsWith('#')).length} Keys</button>
						</div>
					</div>
				</div>
			{/if}
		{/if}

		<!-- MODELS TAB -->
		{#if activeTab === 'models'}
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-semibold">Facade Models</h2>
				<button
					on:click={() => (showAddModel = true)}
					class="flex items-center gap-1 px-3 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
				>
					<svg xmlns="http://www.w3.org/2000/svg" class="w-4 h-4" viewBox="0 0 20 20" fill="currentColor">
						<path fill-rule="evenodd" d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z" clip-rule="evenodd" />
					</svg>
					Add Model
				</button>
			</div>

			<!-- Add Model Form -->
			{#if showAddModel}
				<div class="bg-gray-50 dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
					<h3 class="text-sm font-semibold mb-3">New Facade Model</h3>
					<div class="grid grid-cols-2 gap-3 mb-3">
						<div>
							<label class="text-xs font-medium mb-1 block">Model ID</label>
							<input
								bind:value={newModel.id}
								placeholder="e.g. claude-opus-4.8"
								class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
							/>
						</div>
						<div>
							<label class="text-xs font-medium mb-1 block">Display Name</label>
							<input
								bind:value={newModel.name}
								placeholder="e.g. Claude Opus 4.8"
								class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
							/>
						</div>
					</div>
					<div class="mb-3">
						<label class="text-xs font-medium mb-1 block">Default Tier</label>
						<select
							bind:value={newModel.tier}
							class="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
						>
							<option value="paid">Paid</option>
							<option value="free">Free</option>
						</select>
					</div>

					<!-- Backends -->
					<div class="mb-3">
						<label class="text-xs font-medium mb-2 block">Backend Providers (fallback order)</label>
						{#each newModel.backends as backend, i}
							<div class="flex gap-2 mb-2">
								<select
									bind:value={newModel.backends[i].provider}
									class="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
								>
									<option value="">Select provider</option>
									{#each providers as p}
										<option value={p.id}>{p.name || p.id}</option>
									{/each}
								</select>
								<input
									bind:value={newModel.backends[i].model}
									placeholder="Backend model ID"
									class="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
								/>
								{#if newModel.backends.length > 1}
									<button
										on:click={() => { newModel.backends = newModel.backends.filter((_, idx) => idx !== i); }}
										class="text-red-500 hover:text-red-700 text-sm px-2"
									>X</button>
								{/if}
							</div>
						{/each}
						<button
							on:click={() => { newModel.backends = [...newModel.backends, { provider: '', model: '' }]; }}
							class="text-xs text-blue-500 hover:text-blue-700"
						>+ Add fallback provider</button>
					</div>

					<div class="flex gap-2">
						<button on:click={createModel} class="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition">Create</button>
						<button on:click={() => (showAddModel = false)} class="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-300 dark:hover:bg-gray-700 transition">Cancel</button>
					</div>
				</div>
			{/if}

			<!-- Model List -->
			<div class="flex flex-col gap-2">
				{#each facadeModels as model}
					<div class="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-800 p-4">
						{#if editingModel?.id === model.id}
							<!-- Edit mode -->
							<div class="flex flex-col gap-3">
								<div class="grid grid-cols-2 gap-3">
									<div>
										<label class="text-xs font-medium mb-1 block">Model ID</label>
										<input value={editingModel.id} disabled class="w-full rounded-lg border bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm text-gray-400" />
									</div>
									<div>
										<label class="text-xs font-medium mb-1 block">Display Name</label>
										<input bind:value={editingModel.name} class="w-full rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm" />
									</div>
								</div>

								<div>
									<label class="text-xs font-medium mb-2 block">Backend Providers</label>
									{#each editingModel.backends as backend, i}
										<div class="flex gap-2 mb-2">
											<select
												bind:value={editingModel.backends[i].provider}
												class="rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
											>
												<option value="">Select provider</option>
												{#each providers as p}
													<option value={p.id}>{p.name || p.id}</option>
												{/each}
											</select>
											<input
												bind:value={editingModel.backends[i].model}
												placeholder="Backend model ID"
												class="flex-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-900 px-3 py-2 text-sm"
											/>
											{#if editingModel.backends.length > 1}
												<button
													on:click={() => { editingModel.backends = editingModel.backends.filter((_, idx) => idx !== i); }}
													class="text-red-500 hover:text-red-700 text-sm px-2"
												>X</button>
											{/if}
										</div>
									{/each}
									<button
										on:click={() => { editingModel.backends = [...editingModel.backends, { provider: '', model: '' }]; }}
										class="text-xs text-blue-500 hover:text-blue-700"
									>+ Add fallback</button>
								</div>

								<div class="flex gap-2">
									<button on:click={() => updateModel(editingModel)} class="px-4 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700 transition">Save</button>
									<button on:click={() => (editingModel = null)} class="px-4 py-2 bg-gray-200 dark:bg-gray-800 text-sm rounded-lg transition">Cancel</button>
								</div>
							</div>
						{:else}
							<!-- Display mode -->
							<div class="flex items-center justify-between">
								<div class="flex items-center gap-3">
									<span class="font-semibold">{model.name}</span>
									<span class="text-xs font-mono text-gray-400">{model.id}</span>

									<button on:click={() => toggleModelTier(model)}>
										{#if model.tier === 'free'}
											<span class="text-xs font-bold px-2 py-0.5 rounded-full bg-green-500/20 text-green-600 dark:text-green-400 uppercase cursor-pointer hover:bg-green-500/30 transition">
												Free
											</span>
										{:else}
											<span class="text-xs font-bold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-600 dark:text-amber-400 uppercase cursor-pointer hover:bg-amber-500/30 transition">
												Paid
											</span>
										{/if}
									</button>
								</div>

								<div class="flex items-center gap-2">
									<button
										on:click={() => { editingModel = JSON.parse(JSON.stringify(model)); }}
										class="text-xs px-2 py-1 text-blue-500 hover:text-blue-700 transition"
									>Edit</button>
									<button
										on:click={() => deleteModel(model.id)}
										class="text-xs px-2 py-1 text-red-500 hover:text-red-700 transition"
									>Delete</button>
								</div>
							</div>

							<!-- Backends summary -->
							<div class="mt-2 flex flex-wrap gap-1">
								{#each model.backends || [] as backend, i}
									<span class="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded-full text-gray-500">
										{i + 1}. {backend.provider} → {backend.model}
									</span>
								{/each}
							</div>
						{/if}
					</div>
				{/each}

				{#if facadeModels.length === 0}
					<div class="text-center py-8 text-gray-400">
						No facade models configured. Click "Add Model" to create one.
					</div>
				{/if}
			</div>
		{/if}
	{/if}
</div>
