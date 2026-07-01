<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';

	const GW = 'https://webapp-2nd-service-production.up.railway.app';
	const KEY = 'sk-gateway-admin';

	let activeTab: 'settings' | 'subscriptions' | 'history' = 'settings';
	let loading = true;

	// Payment Settings
	let settings = { binance_uid: '', binance_api_key: '', binance_api_secret: '', bep20_address: '', trc20_address: '', binance_proxy: '' };

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

	// Per-user usage + inline plan change
	let usageByEmail: Record<string, any> = {};
	let expandedEmail = '';
	let loadingUsage = '';

	const fmtNum = (n: number) => (n ?? 0).toLocaleString();
	const pct = (used: number, limit: number) => (limit > 0 ? Math.min(100, Math.round((used / limit) * 100)) : 0);
	const fmtReset = (x: number) => {
		x = Math.max(0, Math.floor(x || 0));
		if (x >= 86400) return `${Math.floor(x / 86400)}d ${Math.floor((x % 86400) / 3600)}h`;
		if (x >= 3600) return `${Math.floor(x / 3600)}h ${Math.floor((x % 3600) / 60)}m`;
		return `${Math.max(1, Math.floor(x / 60))}m`;
	};

	async function toggleUsage(email: string) {
		if (expandedEmail === email) { expandedEmail = ''; return; }
		expandedEmail = email;
		if (!usageByEmail[email]) {
			loadingUsage = email;
			try {
				const res = await fetch(`${GW}/api/usage?email=${encodeURIComponent(email)}`);
				usageByEmail[email] = await res.json();
				usageByEmail = usageByEmail;
			} catch (e) { toast.error('Could not load usage'); }
			loadingUsage = '';
		}
	}

	async function changePlan(email: string, packageId: string) {
		if (!packageId) return;
		try {
			await gw(`/admin/subscriptions/${encodeURIComponent(email)}/grant`, 'POST', { package_id: packageId, months: 1 });
			toast.success(`${email} \u2192 ${packageId}`);
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

	let testing = false;
	let testResult: any = null;
	async function testBinanceProxy() {
		testing = true; testResult = null;
		try {
			await gw('/admin/payment-settings', 'PUT', settings);
			testResult = await gw('/admin/test-binance-proxy', 'POST', {});
		} catch (e: any) { toast.error(e.message); testResult = { ok: false, error: e.message }; }
		testing = false;
	}

	onMount(() => loadAll());
</script>

<div class="flex flex-col h-full overflow-y-auto">
	<div class="px-6 pt-5 pb-3">
		<div class="flex flex-wrap items-center justify-between mb-1 gap-2">
			<h1 class="text-2xl font-bold">Payments & Subscriptions</h1>
			<button on:click={loadAll} class="text-xs px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-lg hover:bg-gray-700 transition">Refresh</button>
		</div>

		<!-- Tabs -->
		<div class="flex gap-1 mt-3 border-b border-gray-200 dark:border-gray-800 overflow-x-auto scrollbar-none">
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
			<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">💰</span> Binance Pay (Personal Account)</h3>
				<p class="text-xs text-gray-500 mb-4">Users can pay via Binance Pay transfer to your personal UID. Verified automatically via Binance API.</p>
				<div class="grid grid-cols-1 gap-3">
					<div>
						<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Binance UID</label>
						<input bind:value={settings.binance_uid} placeholder="Your Binance personal UID (e.g. 123456789)"
							class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
					</div>
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
						<div>
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Binance API Key</label>
							<input type="password" bind:value={settings.binance_api_key} placeholder="For auto-verification of incoming payments"
								class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
						</div>
						<div>
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Binance API Secret</label>
							<input type="password" bind:value={settings.binance_api_secret} placeholder="Keep this secret"
								class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
						</div>
					</div>
					<p class="text-[11px] text-gray-600">Create API key at Binance → Account → API Management. Enable "Read" permission only. No trading needed.</p>
					<div class="mt-4 pt-4 border-t border-gray-200 dark:border-gray-800">
						<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Outbound Proxy (SOCKS5 / HTTP) — optional</label>
						<input bind:value={settings.binance_proxy} placeholder="socks5://user:pass@host:port"
							class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
						<p class="text-[11px] text-gray-600 mt-1">Routes Binance API calls through this proxy (useful where Binance is geo-blocked). Leave empty to connect directly.</p>
						<div class="flex items-center gap-3 mt-3">
							<button on:click={testBinanceProxy} disabled={testing}
								class="px-4 py-2 bg-emerald-700 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-emerald-600 transition disabled:opacity-50">
								{testing ? 'Testing…' : 'Test Binance + Proxy'}
							</button>
							{#if testResult}
								<span class="text-xs font-bold {testResult.ok ? 'text-emerald-400' : 'text-red-400'}">
									{testResult.ok ? '✓ Working' : '✗ Failed'}
								</span>
							{/if}
						</div>
						{#if testResult}
							<div class="mt-3 bg-gray-50 dark:bg-gray-950/60 rounded-lg border border-gray-200 dark:border-gray-800 p-3 text-xs space-y-1 font-mono">
								<div>Proxy: <span class="text-gray-600 dark:text-gray-400">{testResult.proxy || '(none — direct connection)'}</span></div>
								<div>Egress IP: <span class="text-gray-600 dark:text-gray-400">{testResult.egress_ip || testResult.egress_ip_error || '—'}</span></div>
								<div>Binance ping:
									<span class={testResult.binance_ping?.ok ? 'text-emerald-400' : 'text-red-400'}>
										{testResult.binance_ping?.ok ? `OK (${testResult.binance_ping.latency_ms}ms)` : (testResult.binance_ping?.error || 'failed')}
									</span>
								</div>
								<div>Binance API:
									{#if testResult.binance_api?.configured}
										<span class={testResult.binance_api?.ok ? 'text-emerald-400' : 'text-red-400'}>
											{testResult.binance_api?.ok ? 'OK (authenticated)' : ('error: ' + JSON.stringify(testResult.binance_api?.error))}
										</span>
									{:else}
										<span class="text-gray-500">not configured (add API key + secret above to test auth)</span>
									{/if}
								</div>
							</div>
						{/if}
					</div>
				</div>
			</div>

			<!-- BEP20 -->
			<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">🔗</span> BEP20 USDT (BSC Network)</h3>
				<p class="text-xs text-gray-500 mb-4">Users send USDT on BNB Smart Chain. Verified on-chain via BSCScan.</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Your BEP20 USDT Address</label>
					<input bind:value={settings.bep20_address} placeholder="0x..."
						class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
				</div>
			</div>

			<!-- TRC20 -->
			<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 p-5">
				<h3 class="font-semibold mb-1 flex items-center gap-2"><span class="text-lg">⚡</span> TRC20 USDT (TRON Network)</h3>
				<p class="text-xs text-gray-500 mb-4">Users send USDT on TRON network. Low fees. Verified via TronScan.</p>
				<div>
					<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Your TRC20 USDT Address</label>
					<input bind:value={settings.trc20_address} placeholder="T..."
						class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
				</div>
			</div>

			<button on:click={saveSettings}
				class="px-6 py-2.5 bg-blue-600 text-gray-900 dark:text-white rounded-lg hover:bg-blue-700 transition font-medium">
				Save Payment Settings
			</button>
		</div>

	{:else if activeTab === 'subscriptions'}
		<!-- Subscriptions -->
		<div class="px-6 pb-6">
			<div class="flex justify-end mb-4">
				<button on:click={() => { showGrant = !showGrant; }}
					class="text-xs px-3 py-1.5 bg-blue-600 text-gray-900 dark:text-white rounded-lg hover:bg-blue-700 transition">+ Grant Subscription</button>
			</div>

			{#if showGrant}
				<div class="mb-4 bg-white dark:bg-gray-900 rounded-xl p-5 border border-gray-200 dark:border-gray-800">
					<h3 class="text-sm font-semibold mb-3">Grant Subscription (no payment required)</h3>
					<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
						<div>
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">User Email</label>
							<input bind:value={grantForm.email} placeholder="user@example.com"
								class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm" />
						</div>
						<div>
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Package</label>
							<select bind:value={grantForm.package_id} class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm">
								{#each packages.filter(p => p.id !== 'free') as pkg}
									<option value={pkg.id}>{pkg.name}</option>
								{/each}
							</select>
						</div>
						<div>
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Duration (months)</label>
							<input type="number" min="1" bind:value={grantForm.months}
								class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm" />
						</div>
					</div>
					<div class="flex gap-2">
						<button on:click={grantSub} class="px-4 py-2 bg-green-700 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-green-600 transition">Grant</button>
						<button on:click={() => { showGrant = false; }} class="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-sm rounded-lg hover:bg-gray-700 transition">Cancel</button>
					</div>
				</div>
			{/if}

			<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 dark:border-gray-800 text-left text-xs text-gray-500">
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
							<tr class="border-b border-gray-200 dark:border-gray-800/50 hover:bg-gray-800/30 transition {expired ? 'opacity-50' : ''}">
								<td data-label="Email" class="px-4 py-3 font-mono text-xs">{sub.email}</td>
								<td data-label="Package" class="px-4 py-3">{sub.package_name}</td>
								<td data-label="Tier" class="px-4 py-3">
									<span class="text-[11px] font-bold px-2 py-0.5 rounded-full {sub.tier === 'enterprise' ? 'bg-purple-500/20 text-purple-400' : sub.tier === 'pro' ? 'bg-blue-500/20 text-blue-400' : 'bg-green-500/20 text-green-400'} uppercase">{sub.tier}</span>
								</td>
								<td data-label="Method" class="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">{sub.payment_method || '—'}</td>
								<td data-label="Started" class="px-4 py-3 text-xs text-gray-500">{sub.started_at ? sub.started_at.slice(0, 10) : '—'}</td>
								<td data-label="Expires" class="px-4 py-3 text-xs {expired ? 'text-red-400' : 'text-gray-500'}">{sub.expires_at ? sub.expires_at.slice(0, 10) : '—'} {expired ? '(expired)' : ''}</td>
								<td data-label="Actions" class="px-4 py-3 text-right whitespace-nowrap">
									<div class="inline-flex items-center gap-2 justify-end">
										<select class="text-xs rounded-lg border border-gray-300 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-2 py-1"
											on:change={(e) => { changePlan(sub.email, e.currentTarget.value); e.currentTarget.value = ''; }}>
											<option value="" disabled selected>Change plan\u2026</option>
											{#each packages.filter((p) => p.id !== 'free') as pkg}
												<option value={pkg.id} disabled={pkg.id === sub.package_id}>{pkg.name}{pkg.id === sub.package_id ? ' (current)' : ''}</option>
											{/each}
										</select>
										<button on:click={() => toggleUsage(sub.email)} class="text-blue-500 hover:text-blue-400 text-xs">Usage</button>
										<button on:click={() => revokeSub(sub.email)} class="text-red-500 hover:text-red-400 text-xs">Revoke</button>
									</div>
								</td>
							</tr>
							{#if expandedEmail === sub.email}
								<tr class="border-b border-gray-200 dark:border-gray-800/50 bg-gray-50 dark:bg-gray-800/20">
									<td colspan="7" class="px-4 py-3">
										{#if loadingUsage === sub.email}
											<div class="text-xs text-gray-500">Loading usage\u2026</div>
										{:else if usageByEmail[sub.email]?.limits}
											<div class="flex flex-col gap-3 max-w-xl">
												{#each usageByEmail[sub.email].limits as l}
													<div>
														<div class="flex justify-between text-xs mb-1 gap-3">
															<span class="text-gray-700 dark:text-gray-300 font-medium">{l.label}</span>
															<span class="text-gray-500">{fmtNum(l.used)}{l.limit ? ` / ${fmtNum(l.limit)}` : ''} {l.unit}{l.used > 0 ? ` \u00b7 resets ${fmtReset(l.resets_in_seconds)}` : ''}</span>
														</div>
														<div class="w-full h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
															<div class="h-full rounded-full {pct(l.used, l.limit) >= 90 ? 'bg-red-500' : 'bg-[#d4a574]'}" style="width: {l.limit ? pct(l.used, l.limit) : 0}%"></div>
														</div>
													</div>
												{/each}
											</div>
										{:else}
											<div class="text-xs text-gray-500">No usage data.</div>
										{/if}
									</td>
								</tr>
							{/if}
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

			<div class="bg-white dark:bg-gray-900/50 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="border-b border-gray-200 dark:border-gray-800 text-left text-xs text-gray-500">
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
							<tr class="border-b border-gray-200 dark:border-gray-800/50 hover:bg-gray-800/30 transition">
								<td data-label="User" class="px-4 py-3 font-mono text-xs">{payment.user_email}</td>
								<td data-label="Package" class="px-4 py-3">{payment.package_id}</td>
								<td data-label="Amount" class="px-4 py-3">{payment.amount > 0 ? `$${payment.amount}` : 'Free'}</td>
								<td data-label="Method" class="px-4 py-3 text-xs text-gray-600 dark:text-gray-400">{payment.method}</td>
								<td data-label="TX Hash" class="px-4 py-3 font-mono text-[11px] text-gray-500 max-w-[120px] truncate" title={payment.tx_hash || payment.coupon_code || ''}>{payment.tx_hash || payment.coupon_code || '—'}</td>
								<td data-label="Status" class="px-4 py-3">
									<span class="text-[11px] font-bold px-2 py-0.5 rounded-full {payment.status === 'completed' ? 'bg-green-500/20 text-green-400' : payment.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400'} uppercase">{payment.status}</span>
								</td>
								<td data-label="Date" class="px-4 py-3 text-xs text-gray-500">{payment.created_at ? payment.created_at.slice(0, 10) : '—'}</td>
								<td data-label="Actions" class="px-4 py-3 text-right">
									{#if payment.status === 'pending'}
										<button on:click={() => approvePayment(payment.id)} class="text-xs px-2 py-1 bg-green-700 text-gray-900 dark:text-white rounded hover:bg-green-600 transition mr-1">Approve</button>
										<button on:click={() => rejectPayment(payment.id)} class="text-xs px-2 py-1 bg-red-700 text-gray-900 dark:text-white rounded hover:bg-red-600 transition">Reject</button>
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
