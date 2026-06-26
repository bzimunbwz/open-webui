<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	const GW = 'https://webapp-2nd-service-production.up.railway.app';
	const KEY = 'sk-gateway-admin';

	let packages: any[] = [];
	let facadeModels: any[] = [];
	let loading = true;
	let showForm = false;
	let editingPkg: any = null;

	let form = { id: '', name: '', tier: 'pro', description: '', models: [] as string[], price_monthly: 0, price_yearly: 0, features: [''], active: true, order: 0 };

	async function gw(path: string, method = 'GET', body?: any) {
		const res = await fetch(`${GW}${path}`, {
			method,
			headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${KEY}` },
			...(body ? { body: JSON.stringify(body) } : {})
		});
		const text = await res.text();
		if (!res.ok) throw new Error(text);
		return JSON.parse(text);
	}

	async function loadAll() {
		loading = true;
		try {
			const [pkgRes, mdlRes] = await Promise.all([gw('/admin/packages'), gw('/admin/models')]);
			packages = (pkgRes.packages || []).sort((a: any, b: any) => (a.order || 0) - (b.order || 0));
			facadeModels = mdlRes.models || [];
		} catch (e: any) { toast.error(e.message); }
		loading = false;
	}

	function startEdit(pkg: any) {
		editingPkg = pkg;
		form = {
			id: pkg.id,
			name: pkg.name,
			tier: pkg.tier || 'pro',
			description: pkg.description || '',
			models: pkg.models || [],
			price_monthly: pkg.price_monthly || 0,
			price_yearly: pkg.price_yearly || 0,
			features: pkg.features?.length ? [...pkg.features] : [''],
			active: pkg.active !== false,
			order: pkg.order || 0,
		};
		showForm = true;
	}

	function startNew() {
		editingPkg = null;
		form = { id: '', name: '', tier: 'pro', description: '', models: [], price_monthly: 0, price_yearly: 0, features: [''], active: true, order: packages.length };
		showForm = true;
	}

	async function save() {
		try {
			const payload = { ...form, features: form.features.filter(f => f.trim()) };
			if (editingPkg) {
				await gw(`/admin/packages/${form.id}`, 'PUT', payload);
				toast.success(`"${form.name}" updated`);
			} else {
				if (!form.id || !form.name) { toast.error('ID and Name required'); return; }
				await gw('/admin/packages', 'POST', payload);
				toast.success(`"${form.name}" created`);
			}
			showForm = false;
			editingPkg = null;
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function deletePkg(id: string, name: string) {
		if (!confirm(`Delete package "${name}"?`)) return;
		try {
			await gw(`/admin/packages/${id}`, 'DELETE');
			toast.success(`"${name}" deleted`);
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	function toggleModel(modelId: string) {
		if (form.models.includes(modelId)) {
			form.models = form.models.filter(m => m !== modelId);
		} else {
			form.models = [...form.models, modelId];
		}
	}

	onMount(() => loadAll());
</script>

<div class="flex flex-col h-full overflow-y-auto">
	<div class="px-6 pt-5 pb-3">
		<div class="flex items-center justify-between mb-1">
			<h1 class="text-2xl font-bold">Subscription Packages</h1>
			<div class="flex gap-2">
				<button on:click={loadAll} class="text-xs px-3 py-1.5 bg-gray-800 rounded-lg hover:bg-gray-700 transition">Refresh</button>
				<button on:click={startNew} class="text-xs px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition">+ New Package</button>
			</div>
		</div>
		<p class="text-sm text-gray-500">Create and manage subscription tiers. Assign facade models to each package.</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="animate-spin w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full"></div>
		</div>
	{:else}

	<!-- Form -->
	{#if showForm}
		<div class="mx-6 mb-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
			<h3 class="text-sm font-semibold mb-3">{editingPkg ? `Edit: ${form.name}` : 'New Package'}</h3>

			<div class="grid grid-cols-4 gap-3 mb-3">
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Package ID</label>
					<input bind:value={form.id} placeholder="e.g. pro" disabled={!!editingPkg}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm {editingPkg ? 'opacity-50' : ''}" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Display Name</label>
					<input bind:value={form.name} placeholder="e.g. Pro Plan"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Tier Level</label>
					<select bind:value={form.tier} class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm">
						<option value="free">Free</option>
						<option value="pro">Pro</option>
						<option value="enterprise">Enterprise</option>
					</select>
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Sort Order</label>
					<input type="number" bind:value={form.order}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
			</div>

			<div class="mb-3">
				<label class="text-xs text-gray-400 mb-1 block">Description</label>
				<input bind:value={form.description} placeholder="Short description of what's included"
					class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
			</div>

			<div class="grid grid-cols-2 gap-3 mb-3">
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Monthly Price (USDT)</label>
					<input type="number" step="0.01" bind:value={form.price_monthly}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Yearly Price (USDT)</label>
					<input type="number" step="0.01" bind:value={form.price_yearly}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
			</div>

			<!-- Features -->
			<div class="mb-3">
				<label class="text-xs text-gray-400 mb-1 block">Features (shown on pricing page)</label>
				{#each form.features as feature, i}
					<div class="flex gap-2 mb-1">
						<input bind:value={form.features[i]} placeholder="Feature description"
							class="flex-1 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
						<button on:click={() => { form.features = form.features.filter((_, j) => j !== i); }}
							class="text-red-500 hover:text-red-400 px-2">✕</button>
					</div>
				{/each}
				<button on:click={() => { form.features = [...form.features, '']; }}
					class="text-xs text-orange-400 hover:text-orange-300 mt-1">+ Add feature</button>
			</div>

			<!-- Model access -->
			<div class="mb-3">
				<label class="text-xs text-gray-400 mb-2 block">Model Access (leave empty = all paid models based on tier)</label>
				<div class="flex flex-wrap gap-2">
					{#each facadeModels as model}
						<button
							on:click={() => toggleModel(model.id)}
							class="text-xs px-3 py-1.5 rounded-lg border transition {form.models.includes(model.id) ? 'bg-orange-600 border-orange-500 text-white' : 'bg-gray-800 border-gray-700 text-gray-400 hover:border-gray-600'}"
						>{model.name}</button>
					{/each}
				</div>
			</div>

			<!-- Active toggle -->
			<div class="flex items-center gap-2 mb-4">
				<button
					on:click={() => { form.active = !form.active; }}
					class="w-10 h-5 rounded-full transition relative {form.active ? 'bg-green-500' : 'bg-gray-600'}"
				>
					<span class="absolute top-0.5 {form.active ? 'right-0.5' : 'left-0.5'} w-4 h-4 rounded-full bg-white transition-all shadow"></span>
				</button>
				<span class="text-sm text-gray-400">{form.active ? 'Active' : 'Inactive'}</span>
			</div>

			<div class="flex gap-2">
				<button on:click={save} class="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition">{editingPkg ? 'Save' : 'Create'}</button>
				<button on:click={() => { showForm = false; editingPkg = null; }} class="px-4 py-2 bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
			</div>
		</div>
	{/if}

	<!-- Package Cards -->
	<div class="grid grid-cols-1 md:grid-cols-3 gap-4 px-6 pb-6">
		{#each packages as pkg (pkg.id)}
			<div class="bg-gray-900/50 rounded-xl border border-gray-800 p-5 flex flex-col {!pkg.active ? 'opacity-50' : ''}">
				<div class="flex items-center justify-between mb-2">
					<h3 class="font-bold text-lg">{pkg.name}</h3>
					<span class="text-[11px] font-bold px-2 py-0.5 rounded-full {pkg.tier === 'enterprise' ? 'bg-purple-500/20 text-purple-400' : pkg.tier === 'pro' ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400'} uppercase">{pkg.tier}</span>
				</div>

				<p class="text-xs text-gray-500 mb-3">{pkg.description || 'No description'}</p>

				<div class="flex gap-3 mb-3">
					<div>
						<span class="text-xl font-bold">${pkg.price_monthly}</span>
						<span class="text-xs text-gray-500">/mo</span>
					</div>
					<div>
						<span class="text-xl font-bold">${pkg.price_yearly}</span>
						<span class="text-xs text-gray-500">/yr</span>
					</div>
				</div>

				{#if pkg.features?.length}
					<ul class="text-xs text-gray-400 mb-3 space-y-1 flex-1">
						{#each pkg.features as feature}
							<li class="flex items-start gap-1"><span class="text-green-500">✓</span> {feature}</li>
						{/each}
					</ul>
				{/if}

				{#if pkg.models?.length}
					<div class="text-xs text-gray-500 mb-3">{pkg.models.length} specific models assigned</div>
				{:else}
					<div class="text-xs text-gray-500 mb-3">All {pkg.tier}-tier models</div>
				{/if}

				<div class="flex gap-2 mt-auto">
					<button on:click={() => startEdit(pkg)} class="flex-1 text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition">Edit</button>
					{#if pkg.id !== 'free'}
						<button on:click={() => deletePkg(pkg.id, pkg.name)} class="text-xs px-3 py-1.5 text-red-400 hover:text-red-300 transition">Delete</button>
					{/if}
				</div>
			</div>
		{/each}
	</div>
	{/if}
</div>
