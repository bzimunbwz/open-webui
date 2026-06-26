<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	const GW = 'https://webapp-2nd-service-production.up.railway.app';
	const KEY = 'sk-gateway-admin';

	let coupons: any[] = [];
	let packages: any[] = [];
	let loading = true;
	let showForm = false;
	let selectedGroup = '';
	let searchQuery = '';
	let copiedText = '';

	// Form
	let form = {
		count: 1,
		group: '',
		package_id: '',
		duration: 'monthly',
		months: 1,
		max_uses: 1,
		prefix: '',
		expires_at: '',
		active: true,
	};

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
			const [cRes, pRes] = await Promise.all([gw('/admin/coupons'), gw('/admin/packages')]);
			coupons = cRes.coupons || [];
			packages = pRes.packages || [];
		} catch (e: any) { toast.error(e.message); }
		loading = false;
	}

	async function createCoupons() {
		if (!form.group && form.count > 1) {
			form.group = `batch-${new Date().toISOString().slice(0, 10)}`;
		}
		try {
			const res = await gw('/admin/coupons', 'POST', form);
			toast.success(`Created ${res.count} coupon(s)`);
			showForm = false;
			await loadAll();

			// Auto-show created codes for copying
			if (res.codes?.length) {
				copiedText = res.codes.join('\n');
			}
		} catch (e: any) { toast.error(e.message); }
	}

	async function deleteCoupon(code: string) {
		if (!confirm(`Delete coupon "${code}"?`)) return;
		try {
			await gw(`/admin/coupons/${code}`, 'DELETE');
			toast.success('Deleted');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function deleteGroup(group: string) {
		if (!confirm(`Delete ALL coupons in group "${group}"?`)) return;
		try {
			const res = await gw(`/admin/coupons/group/${encodeURIComponent(group)}`, 'DELETE');
			toast.success(`Deleted ${res.count} coupons from "${group}"`);
			selectedGroup = '';
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function toggleCoupon(coupon: any) {
		try {
			await gw(`/admin/coupons/${coupon.code}`, 'PUT', { active: !coupon.active });
			toast.success(coupon.active ? 'Deactivated' : 'Activated');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		toast.success('Copied to clipboard');
	}

	function copySingle(code: string) {
		navigator.clipboard.writeText(code);
		toast.success(`Copied: ${code}`);
	}

	function copyGroup(group: string) {
		const codes = coupons.filter(c => c.group === group).map(c => c.code).join('\n');
		navigator.clipboard.writeText(codes);
		toast.success(`Copied ${coupons.filter(c => c.group === group).length} codes`);
	}

	// Derived
	$: groups = [...new Set(coupons.map(c => c.group || 'ungrouped'))].sort();
	$: filteredCoupons = coupons.filter(c => {
		if (selectedGroup && (c.group || 'ungrouped') !== selectedGroup) return false;
		if (searchQuery) {
			const q = searchQuery.toLowerCase();
			return c.code.toLowerCase().includes(q) || (c.group || '').toLowerCase().includes(q);
		}
		return true;
	});

	onMount(() => loadAll());
</script>

<div class="flex flex-col h-full overflow-y-auto">
	<div class="px-6 pt-5 pb-3">
		<div class="flex items-center justify-between mb-1">
			<h1 class="text-2xl font-bold">Coupons</h1>
			<div class="flex gap-2">
				<button on:click={loadAll} class="text-xs px-3 py-1.5 bg-gray-800 rounded-lg hover:bg-gray-700 transition">Refresh</button>
				<button on:click={() => { showForm = true; }} class="text-xs px-3 py-1.5 bg-orange-600 text-white rounded-lg hover:bg-orange-700 transition">+ Create Coupons</button>
			</div>
		</div>
		<p class="text-sm text-gray-500">Create single or bulk coupons. Group coupons for easy management. 1 coupon = 1 use per user.</p>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="animate-spin w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full"></div>
		</div>
	{:else}

	<!-- Create Form -->
	{#if showForm}
		<div class="mx-6 mb-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
			<h3 class="text-sm font-semibold mb-3">Create Coupons</h3>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Quantity</label>
					<input type="number" min="1" max="1000" bind:value={form.count}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Group Name</label>
					<input bind:value={form.group} placeholder="e.g. launch-promo"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Code Prefix</label>
					<input bind:value={form.prefix} placeholder="e.g. PROMO"
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Max Uses Per Coupon</label>
					<input type="number" min="1" bind:value={form.max_uses}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-3">
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Package</label>
					<select bind:value={form.package_id} class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm">
						<option value="">Any package</option>
						{#each packages as pkg}
							<option value={pkg.id}>{pkg.name}</option>
						{/each}
					</select>
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Duration Type</label>
					<select bind:value={form.duration} class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm">
						<option value="monthly">Monthly</option>
						<option value="yearly">Yearly</option>
					</select>
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Months Valid</label>
					<input type="number" min="1" bind:value={form.months}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Expires At (optional)</label>
					<input type="date" bind:value={form.expires_at}
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
				</div>
			</div>
			<div class="flex gap-2">
				<button on:click={createCoupons} class="px-4 py-2 bg-orange-600 text-white text-sm rounded-lg hover:bg-orange-700 transition">Create {form.count > 1 ? `${form.count} Coupons` : 'Coupon'}</button>
				<button on:click={() => { showForm = false; }} class="px-4 py-2 bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
			</div>
		</div>
	{/if}

	<!-- Created codes display -->
	{#if copiedText}
		<div class="mx-6 mb-4 bg-green-900/30 rounded-xl p-4 border border-green-800">
			<div class="flex items-center justify-between mb-2">
				<span class="text-sm font-semibold text-green-400">Created Codes</span>
				<div class="flex gap-2">
					<button on:click={() => copyToClipboard(copiedText)} class="text-xs px-3 py-1 bg-green-700 text-white rounded-lg hover:bg-green-600 transition">Copy All</button>
					<button on:click={() => { copiedText = ''; }} class="text-xs text-gray-400 hover:text-gray-300">Dismiss</button>
				</div>
			</div>
			<pre class="text-xs font-mono text-green-300 max-h-40 overflow-y-auto">{copiedText}</pre>
		</div>
	{/if}

	<!-- Filters -->
	<div class="px-6 mb-4 flex flex-wrap gap-3 items-center">
		<div class="relative flex-1 max-w-full sm:max-w-xs">
			<input bind:value={searchQuery} placeholder="Search coupons..."
				class="w-full rounded-lg border border-gray-700 bg-gray-800 pl-8 pr-3 py-2 text-sm" />
			<svg class="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-gray-500" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
				<path fill-rule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clip-rule="evenodd" />
			</svg>
		</div>
		<select bind:value={selectedGroup} class="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm">
			<option value="">All Groups ({coupons.length})</option>
			{#each groups as group}
				<option value={group}>{group} ({coupons.filter(c => (c.group || 'ungrouped') === group).length})</option>
			{/each}
		</select>
		{#if selectedGroup}
			<button on:click={() => copyGroup(selectedGroup)} class="text-xs px-3 py-1.5 bg-gray-700 rounded-lg hover:bg-gray-600 transition">Copy Group</button>
			<button on:click={() => deleteGroup(selectedGroup)} class="text-xs px-3 py-1.5 text-red-400 hover:text-red-300 transition">Delete Group</button>
		{/if}
	</div>

	<!-- Coupon Table -->
	<div class="px-6 pb-6">
		<div class="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden">
			<table class="w-full text-sm">
				<thead>
					<tr class="border-b border-gray-800 text-left text-xs text-gray-500">
						<th class="px-4 py-3">Code</th>
						<th class="px-4 py-3">Group</th>
						<th class="px-4 py-3">Package</th>
						<th class="px-4 py-3">Duration</th>
						<th class="px-4 py-3">Used</th>
						<th class="px-4 py-3">Status</th>
						<th class="px-4 py-3">Expires</th>
						<th class="px-4 py-3 text-right">Actions</th>
					</tr>
				</thead>
				<tbody>
					{#each filteredCoupons as coupon (coupon.code)}
						<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
							<td data-label="Code" class="px-4 py-3">
								<button on:click={() => copySingle(coupon.code)} class="font-mono text-orange-400 hover:text-orange-300 cursor-pointer" title="Click to copy">
									{coupon.code}
								</button>
							</td>
							<td data-label="Group" class="px-4 py-3 text-gray-500">{coupon.group || '—'}</td>
							<td data-label="Package" class="px-4 py-3">{coupon.package_id || 'Any'}</td>
							<td data-label="Duration" class="px-4 py-3 text-gray-400">{coupon.duration} ({coupon.months}mo)</td>
							<td data-label="Used" class="px-4 py-3">
								<span class="{(coupon.used_by || []).length >= (coupon.max_uses || 1) ? 'text-red-400' : 'text-gray-400'}">
									{(coupon.used_by || []).length}/{coupon.max_uses || 1}
								</span>
							</td>
							<td data-label="Status" class="px-4 py-3">
								<button on:click={() => toggleCoupon(coupon)}
									class="text-[11px] font-bold px-2 py-0.5 rounded-full cursor-pointer {coupon.active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}">
									{coupon.active ? 'ACTIVE' : 'INACTIVE'}
								</button>
							</td>
							<td data-label="Expires" class="px-4 py-3 text-xs text-gray-500">{coupon.expires_at ? coupon.expires_at.slice(0, 10) : 'Never'}</td>
							<td data-label="Actions" class="px-4 py-3 text-right">
								<button on:click={() => deleteCoupon(coupon.code)} class="text-red-500 hover:text-red-400 text-xs">Delete</button>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>

			{#if filteredCoupons.length === 0}
				<div class="text-center py-12 text-gray-500">
					{searchQuery || selectedGroup ? 'No matching coupons' : 'No coupons yet. Click "Create Coupons" to get started.'}
				</div>
			{/if}
		</div>
	</div>
	{/if}
</div>
