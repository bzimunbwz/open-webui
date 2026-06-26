<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	const GW = 'https://webapp-2nd-service-production.up.railway.app';
	const KEY = 'sk-gateway-admin';

	let activeTab: 'settings' | 'subscriptions' | 'history' = 'settings';
	let loading = true;

	// Payment Settings
	let settings = { binance_uid: '', binance_api_key: '', binance_api_secret: '', bep20_address: '', trc20_address: '' };

	// Subscriptions
	let subs: any[] = [];
	let packages: any[] = [];

	// Payment History
	let payments: any[] = [];

	// Grant form
	let showGrant = false;
	let grantForm = { email: '', package_id: 'pro', months: 1 };

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
			const [sRes, pRes, phRes, pkgRes] = await Promise.all([
				gw('/admin/payment-settings'),
				gw('/admin/subscriptions'),
				gw('/admin/payments'),
				gw('/admin/packages'),
			]);
			settings = sRes.settings || settings;
			subs = pRes.subscriptions || [];
			payments = phRes.payments || [];
			packages = pkgRes.packages || [];
		} catch (e: any) { toast.error(e.message); }
		loading = false;
	}

	async function saveSettings() {
		try {
			await gw('/admin/payment-settings', 'PUT', settings);
			toast.success('Payment settings saved');
		} catch (e: any) { toast.error(e.message); }
	}

	async function grantSub() {
		if (!grantForm.email) { toast.error('Email required'); return; }
		try {
			await gw(`/admin/subscriptions/${encodeURIComponent(grantForm.email)}/grant`, 'POST', {
				package_id: grantForm.package_id,
				months: grantForm.months,
			});
			toast.success(`Subscription granted to ${grantForm.email}`);
			showGrant = false;
			grantForm = { email: '', package_id: 'pro', months: 1 };
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function revokeSub(email: string) {
		if (!confirm(`Revoke subscription for ${email}?`)) return;
		try {
			await gw(`/admin/subscriptions/${encodeURIComponent(email)}`, 'DELETE');
			toast.success('Revoked');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function approvePayment(id: string) {
		try {
			await gw(`/admin/payments/${id}/approve`, 'POST');
			toast.success('Payment approved, subscription activated');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	async function rejectPayment(id: string) {
		if (!confirm('Reject this payment?')) return;
		try {
			await gw(`/admin/payments/${id}/reject`, 'POST');
			toast.success('Payment rejected');
			await loadAll();
		} catch (e: any) { toast.error(e.message); }
	}

	$: pendingPayments = payments.filter(p => p.status === 'pending');

	onMount(() => loadAll());
</script>

<div class="flex flex-col h-full overflow-y-auto">
	<div class="px-6 pt-5 pb-3">
		<div class="flex flex-wrap items-center justify-between mb-1 gap-2">
			<h1 class="text-2xl font-bold">Payments & Subscriptions</h1>
			<button on:click={loadAll} class="text-xs px-3 py-1.5 bg-gray-800 rounded-lg hover:bg-gray-700 transition">Refresh</button>
		</div>

		<!-- Tabs -->
		<div class="flex gap-1 mt-3 border-b border-gray-800 overflow-x-auto scrollbar-none">
			<button
				class="whitespace-nowrap flex-shrink-0 px-4 py-2 text-sm font-medium transition border-b-2 {activeTab === 'settings' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}"
				on:click={() => (activeTab = 'settings')}
			>Payment Settings</button>
			<button
				class="whitespace-nowrap flex-shrink-0 px-4 py-2 text-sm font-medium transition border-b-2 {activeTab === 'subscriptions' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}"
				on:click={() => (activeTab = 'subscriptions')}
			>Subscriptions ({subs.length})</button>
			<button
				class="whitespace-nowrap flex-shrink-0 px-4 py-2 text-sm font-medium transition border-b-2 {activeTab === 'history' ? 'border-blue-500 text-blue-400' : 'border-transparent text-gray-500 hover:text-gray-300'}"
				on:click={() => (activeTab = 'history')}
			>Payment History {pendingPayments.length ? `(${pendingPayments.length} pending)` : ''}</button>
		</div>
	</div>

	{#if loading}
		<div class="flex items-center justify-center py-20">
			<div class="animate-spin w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full"></div>
		</div>
	{:else}

	{#if activeTab === 'settings'}
		<!-- Payment Settings -->
		<div class="px-6 pb-6 space-y-4">
			<!-- Binance Pay -->
			<div class="bg-gray-900/50 rounded-xl border border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">💰</span> Binance Pay (Personal Account)</h3>
				<p class="text-xs text-gray-500 mb-4">Users can pay via Binance Pay transfer to your personal UID. Verified automatically via Binance API.</p>
				<div class="grid grid-cols-1 gap-3">
					<div>
						<label class="text-xs text-gray-400 mb-1 block">Binance UID</label>
						<input bind:value={settings.binance_uid} placeholder="Your Binance personal UID (e.g. 123456789)"
							class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono" />
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<div>
							<label class="text-xs text-gray-400 mb-1 block">Binance API Key</label>
							<input type="password" bind:value={settings.binance_api_key} placeholder="For auto-verification of incoming payments"
								class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono" />
						</div>
						<div>
							<label class="text-xs text-gray-400 mb-1 block">Binance API Secret</label>
							<input type="password" bind:value={settings.binance_api_secret} placeholder="Keep this secret"
								class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono" />
						</div>
					</div>
					<p class="text-[11px] text-gray-600">Create API key at Binance → Account → API Management. Enable "Read" permission only. No trading needed.</p>
				</div>
			</div>

			<!-- BEP20 -->
			<div class="bg-gray-900/50 rounded-xl border border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">🔗</span> BEP20 USDT (BSC Network)</h3>
				<p class="text-xs text-gray-500 mb-4">Users send USDT on BNB Smart Chain. Verified on-chain via BSCScan.</p>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Your BEP20 USDT Address</label>
					<input bind:value={settings.bep20_address} placeholder="0x..."
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono" />
				</div>
			</div>

			<!-- TRC20 -->
			<div class="bg-gray-900/50 rounded-xl border border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">⚡</span> TRC20 USDT (TRON Network)</h3>
				<p class="text-xs text-gray-500 mb-4">Users send USDT on TRON network. Low fees. Verified via TronScan.</p>
				<div>
					<label class="text-xs text-gray-400 mb-1 block">Your TRC20 USDT Address</label>
					<input bind:value={settings.trc20_address} placeholder="T..."
						class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm font-mono" />
				</div>
			</div>

			<button on:click={saveSettings}
				class="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-medium">
				Save Payment Settings
			</button>
		</div>

	{:else if activeTab === 'subscriptions'}
		<!-- Subscriptions -->
		<div class="px-6 pb-6">
			<div class="flex justify-end mb-4">
				<button on:click={() => { showGrant = !showGrant; }}
					class="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">+ Grant Subscription</button>
			</div>

			{#if showGrant}
				<div class="mb-4 bg-gray-900 rounded-xl p-5 border border-gray-800">
					<h3 class="text-sm font-semibold mb-3">Grant Subscription (no payment required)</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
						<div>
							<label class="text-xs text-gray-400 mb-1 block">User Email</label>
							<input bind:value={grantForm.email} placeholder="user@example.com"
								class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
						</div>
						<div>
							<label class="text-xs text-gray-400 mb-1 block">Package</label>
							<select bind:value={grantForm.package_id} class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm">
								{#each packages.filter(p => p.id !== 'free') as pkg}
									<option value={pkg.id}>{pkg.name}</option>
								{/each}
							</select>
						</div>
						<div>
							<label class="text-xs text-gray-400 mb-1 block">Duration (months)</label>
							<input type="number" min="1" bind:value={grantForm.months}
								class="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm" />
						</div>
					</div>
					<div class="flex gap-2">
						<button on:click={grantSub} class="px-4 py-2 bg-green-700 text-white text-sm rounded-lg hover:bg-green-600 transition">Grant</button>
						<button on:click={() => { showGrant = false; }} class="px-4 py-2 bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
					</div>
				</div>
			{/if}

			<div class="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-left text-xs text-gray-500">
							<th class="px-4 py-3">Email</th>
							<th class="px-4 py-3">Package</th>
							<th class="px-4 py-3">Tier</th>
							<th class="px-4 py-3">Method</th>
							<th class="px-4 py-3">Started</th>
							<th class="px-4 py-3">Expires</th>
							<th class="px-4 py-3 text-right">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each subs as sub}
							{@const expired = sub.expires_at && new Date(sub.expires_at) < new Date()}
							<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition {expired ? 'opacity-50' : ''}">
								<td data-label="Email" class="px-4 py-3 font-mono text-xs">{sub.email}</td>
								<td data-label="Package" class="px-4 py-3">{sub.package_name}</td>
								<td data-label="Tier" class="px-4 py-3">
									<span class="text-[11px] font-bold px-2 py-0.5 rounded-full {sub.tier === 'enterprise' ? 'bg-purple-500/20 text-purple-400' : sub.tier === 'pro' ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'} uppercase">{sub.tier}</span>
								</td>
								<td data-label="Method" class="px-4 py-3 text-xs text-gray-400">{sub.payment_method || '—'}</td>
								<td data-label="Started" class="px-4 py-3 text-xs text-gray-500">{sub.started_at ? sub.started_at.slice(0, 10) : '—'}</td>
								<td data-label="Expires" class="px-4 py-3 text-xs {expired ? 'text-red-400' : 'text-gray-500'}">{sub.expires_at ? sub.expires_at.slice(0, 10) : '—'} {expired ? '(expired)' : ''}</td>
								<td data-label="Actions" class="px-4 py-3 text-right">
									<button on:click={() => revokeSub(sub.email)} class="text-red-500 hover:text-red-400 text-xs">Revoke</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
				{#if subs.length === 0}
					<div class="text-center py-12 text-gray-500">No active subscriptions</div>
				{/if}
			</div>
		</div>

	{:else if activeTab === 'history'}
		<!-- Payment History -->
		<div class="px-6 pb-6">
			{#if pendingPayments.length > 0}
				<div class="mb-4 bg-yellow-900/20 rounded-xl p-4 border border-yellow-800/50">
					<span class="text-sm font-semibold text-yellow-400">{pendingPayments.length} payment(s) awaiting review</span>
				</div>
			{/if}

			<div class="bg-gray-900/50 rounded-xl border border-gray-800 overflow-hidden overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-800 text-left text-xs text-gray-500">
							<th class="px-4 py-3">User</th>
							<th class="px-4 py-3">Package</th>
							<th class="px-4 py-3">Amount</th>
							<th class="px-4 py-3">Method</th>
							<th class="px-4 py-3">TX Hash</th>
							<th class="px-4 py-3">Status</th>
							<th class="px-4 py-3">Date</th>
							<th class="px-4 py-3 text-right">Actions</th>
						</tr>
					</thead>
					<tbody>
						{#each payments.slice().reverse() as payment}
							<tr class="border-b border-gray-800/50 hover:bg-gray-800/30 transition">
								<td data-label="User" class="px-4 py-3 font-mono text-xs">{payment.user_email}</td>
								<td data-label="Package" class="px-4 py-3">{payment.package_id}</td>
								<td data-label="Amount" class="px-4 py-3">{payment.amount > 0 ? `$${payment.amount}` : 'Free'}</td>
								<td data-label="Method" class="px-4 py-3 text-xs text-gray-400">{payment.method}</td>
								<td data-label="TX Hash" class="px-4 py-3 font-mono text-[11px] text-gray-500 max-w-[120px] truncate" title={payment.tx_hash || payment.coupon_code || ''}>{payment.tx_hash || payment.coupon_code || '—'}</td>
								<td data-label="Status" class="px-4 py-3">
									<span class="text-[11px] font-bold px-2 py-0.5 rounded-full {payment.status === 'completed' ? 'bg-green-500/20 text-green-400' : payment.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'} uppercase">{payment.status}</span>
								</td>
								<td data-label="Date" class="px-4 py-3 text-xs text-gray-500">{payment.created_at ? payment.created_at.slice(0, 10) : '—'}</td>
								<td data-label="Actions" class="px-4 py-3 text-right">
									{#if payment.status === 'pending'}
										<button on:click={() => approvePayment(payment.id)} class="text-xs px-2 py-1 bg-green-700 text-white rounded hover:bg-green-600 transition mr-1">Approve</button>
										<button on:click={() => rejectPayment(payment.id)} class="text-xs px-2 py-1 bg-red-700 text-white rounded hover:bg-red-600 transition">Reject</button>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
				{#if payments.length === 0}
					<div class="text-center py-12 text-gray-500">No payment history</div>
				{/if}
			</div>
		</div>
	{/if}

	{/if}
</div>
