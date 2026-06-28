<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import { toast } from 'svelte-sonner';
	import { user } from '$lib/stores';

	const i18n = getContext('i18n');
	const GW = 'https://webapp-2nd-service-production.up.railway.app';

	let packages: any[] = [];
	let subscription: any = null;
	let paymentInfo: any = null;
	let loading = true;

	// Subscribe form
	let selectedPkg = '';
	let duration: 'monthly' | 'yearly' = 'monthly';
	let paymentMethod = '';
	let couponCode = '';
	let txHash = '';
	let subscribing = false;
	let showPayment = false;

	async function loadAll() {
		loading = true;
		try {
			const [pkgRes, subRes, payRes] = await Promise.all([
				fetch(`${GW}/api/packages`).then(r => r.json()),
				fetch(`${GW}/api/subscription`, { headers: { 'X-User-Email': $user?.email || '' } }).then(r => r.json()),
				fetch(`${GW}/api/payment-info`).then(r => r.json()),
			]);
			packages = pkgRes.packages || [];
			subscription = subRes.subscription || null;
			paymentInfo = payRes || {};
		} catch (e: any) { toast.error(`Failed to load: ${e.message}`); }
		loading = false;
	}

	function selectPackage(pkgId: string) {
		selectedPkg = pkgId;
		showPayment = true;
		paymentMethod = '';
		couponCode = '';
		txHash = '';
	}

	async function subscribe() {
		if (!selectedPkg) return;
		subscribing = true;
		try {
			const body: any = {
				email: $user?.email || '',
				package_id: selectedPkg,
				duration,
			};
			if (couponCode) {
				body.coupon_code = couponCode;
			} else if (paymentMethod && txHash) {
				body.payment_method = paymentMethod;
				body.tx_hash = txHash;
			} else {
				toast.error('Enter a coupon code or provide payment details');
				subscribing = false;
				return;
			}

			const res = await fetch(`${GW}/api/subscribe`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(body),
			});
			const data = await res.json();

			if (!res.ok) {
				const detail = typeof data.detail === 'string' ? JSON.parse(data.detail) : data.detail;
				if (detail?.error === 'payment_pending') {
					toast.success('Payment submitted for review. You will be notified once approved.');
					showPayment = false;
				} else {
					throw new Error(detail?.message || detail?.detail || 'Subscription failed');
				}
			} else {
				toast.success(`Subscribed to ${data.package}! Expires ${data.expires_at?.slice(0, 10)}`);
				showPayment = false;
				await loadAll();
			}
		} catch (e: any) {
			toast.error(e.message);
		}
		subscribing = false;
	}

	function copyAddress(addr: string) {
		navigator.clipboard.writeText(addr);
		toast.success('Address copied');
	}

	$: selectedPkgData = packages.find(p => p.id === selectedPkg);
	$: currentPrice = selectedPkgData ? (duration === 'yearly' ? selectedPkgData.price_yearly : selectedPkgData.price_monthly) : 0;

	onMount(() => loadAll());
</script>

<svelte:head><title>Subscription</title></svelte:head>

<div class="flex flex-col h-full w-full flex-1 overflow-y-auto">
	<div class="max-w-4xl lg:max-w-5xl mx-auto w-full px-4 sm:px-6 py-6 sm:py-8">
		<!-- Current subscription -->
		{#if subscription && subscription.package_id !== 'free'}
			<div class="mb-8 bg-gradient-to-r from-orange-900/30 to-purple-900/30 rounded-2xl p-6 border border-orange-800/50">
				<div class="flex items-center justify-between gap-3 flex-wrap">
					<div>
						<span class="text-xs text-orange-400 uppercase font-bold">Current Plan</span>
						<h2 class="text-xl font-bold mt-1">{subscription.package_name || subscription.package_id}</h2>
						<p class="text-sm text-gray-600 dark:text-gray-400 mt-1">
							Expires: {subscription.expires_at ? subscription.expires_at.slice(0, 10) : 'Never'}
						</p>
					</div>
					<span class="text-[11px] font-bold px-3 py-1 rounded-full bg-orange-500/20 text-orange-400 uppercase">{subscription.tier}</span>
				</div>
			</div>
		{/if}

		<h1 class="text-2xl sm:text-3xl font-bold mb-2 text-center">Choose Your Plan</h1>
		<p class="text-gray-500 text-center mb-6">Unlock premium AI models with a subscription</p>

		<!-- Duration toggle -->
		<div class="flex flex-wrap justify-center gap-2 mb-8">
			<button
				on:click={() => (duration = 'monthly')}
				class="px-4 py-2 rounded-lg text-sm transition {duration === 'monthly' ? 'bg-orange-600 text-gray-900 dark:text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-700'}"
			>Monthly</button>
			<button
				on:click={() => (duration = 'yearly')}
				class="px-4 py-2 rounded-lg text-sm transition {duration === 'yearly' ? 'bg-orange-600 text-gray-900 dark:text-white' : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-700'}"
			>Yearly <span class="text-[10px] ml-1 opacity-75">Save ~17%</span></button>
		</div>

		{#if loading}
			<div class="flex items-center justify-center py-20">
				<div class="animate-spin w-6 h-6 border-2 border-orange-500 border-t-transparent rounded-full"></div>
			</div>
		{:else}
		<!-- Package Cards -->
		<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6 mb-8">
			{#each packages as pkg (pkg.id)}
				{@const isCurrentPlan = subscription?.package_id === pkg.id}
				{@const price = duration === 'yearly' ? pkg.price_yearly : pkg.price_monthly}
				<div class="bg-white dark:bg-gray-900/50 rounded-2xl border {pkg.tier === 'pro' ? 'border-orange-600 ring-1 ring-orange-600/30' : 'border-gray-200 dark:border-gray-800'} p-5 sm:p-6 flex flex-col relative">
					{#if pkg.tier === 'pro'}
						<div class="absolute -top-3 left-1/2 -translate-x-1/2 bg-orange-600 text-gray-900 dark:text-white text-[10px] font-bold px-3 py-1 rounded-full uppercase">Popular</div>
					{/if}

					<h3 class="font-bold text-xl mb-1">{pkg.name}</h3>
					<p class="text-xs text-gray-500 mb-4">{pkg.description}</p>

					<div class="mb-4">
						<span class="text-3xl font-bold">${price}</span>
						<span class="text-sm text-gray-500">/{duration === 'yearly' ? 'year' : 'month'}</span>
					</div>

					{#if pkg.features?.length}
						<ul class="text-sm text-gray-600 dark:text-gray-400 mb-6 space-y-2 flex-1">
							{#each pkg.features as feature}
								<li class="flex items-start gap-2"><span class="text-green-500 mt-0.5">✓</span> {feature}</li>
							{/each}
						</ul>
					{/if}

					{#if isCurrentPlan}
						<button disabled class="w-full py-2.5 rounded-xl bg-gray-700 text-gray-600 dark:text-gray-400 text-sm font-medium cursor-not-allowed">Current Plan</button>
					{:else if pkg.price_monthly === 0}
						<button disabled class="w-full py-2.5 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 text-sm font-medium cursor-not-allowed">Free Forever</button>
					{:else}
						<button on:click={() => selectPackage(pkg.id)}
							class="w-full py-2.5 rounded-xl bg-orange-600 text-gray-900 dark:text-white text-sm font-medium hover:bg-orange-700 transition">
							Subscribe
						</button>
					{/if}
				</div>
			{/each}
		</div>

		<!-- Payment Modal -->
		{#if showPayment && selectedPkgData}
			<div class="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 p-6 max-w-lg mx-auto">
				<h3 class="font-bold text-lg mb-1">Subscribe to {selectedPkgData.name}</h3>
				<p class="text-sm text-gray-500 mb-4">
					{duration === 'yearly' ? 'Yearly' : 'Monthly'} — <strong class="text-gray-900 dark:text-white">${currentPrice} USDT</strong>
				</p>

				<!-- Coupon -->
				<div class="mb-4 p-4 bg-gray-100 dark:bg-gray-800/50 rounded-xl">
					<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block font-medium">Have a coupon?</label>
					<div class="flex gap-2">
						<input bind:value={couponCode} placeholder="Enter coupon code"
							class="flex-1 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono uppercase" />
						{#if couponCode}
							<button on:click={subscribe} disabled={subscribing}
								class="px-4 py-2 bg-green-700 text-gray-900 dark:text-white text-sm rounded-lg hover:bg-green-600 transition disabled:opacity-50">
								{subscribing ? 'Applying...' : 'Apply'}
							</button>
						{/if}
					</div>
				</div>

				{#if currentPrice > 0}
					<div class="text-center text-xs text-gray-600 mb-4">— or pay with crypto —</div>

					<!-- Payment methods -->
					<div class="space-y-3 mb-4">
						{#if paymentInfo?.methods?.binance_pay}
							<button on:click={() => (paymentMethod = 'binance_pay')}
								class="w-full p-4 rounded-xl border transition text-left {paymentMethod === 'binance_pay' ? 'border-orange-500 bg-orange-900/20' : 'border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/50 hover:border-gray-600'}">
								<div class="font-medium text-sm">💰 Binance Pay</div>
								<div class="text-xs text-gray-500 mt-1">Send ${currentPrice} USDT to UID: <strong class="text-gray-700 dark:text-gray-300 cursor-pointer" on:click|stopPropagation={() => copyAddress(paymentInfo.binance_uid)}>{paymentInfo.binance_uid}</strong></div>
							</button>
						{/if}
						{#if paymentInfo?.methods?.bep20}
							<button on:click={() => (paymentMethod = 'bep20')}
								class="w-full p-4 rounded-xl border transition text-left {paymentMethod === 'bep20' ? 'border-orange-500 bg-orange-900/20' : 'border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/50 hover:border-gray-600'}">
								<div class="font-medium text-sm">🔗 BEP20 USDT (BSC)</div>
								<div class="text-xs text-gray-500 mt-1">Send ${currentPrice} USDT to: <strong class="text-gray-700 dark:text-gray-300 cursor-pointer font-mono text-[11px]" on:click|stopPropagation={() => copyAddress(paymentInfo.bep20_address)}>{paymentInfo.bep20_address?.slice(0, 10)}...{paymentInfo.bep20_address?.slice(-6)}</strong></div>
							</button>
						{/if}
						{#if paymentInfo?.methods?.trc20}
							<button on:click={() => (paymentMethod = 'trc20')}
								class="w-full p-4 rounded-xl border transition text-left {paymentMethod === 'trc20' ? 'border-orange-500 bg-orange-900/20' : 'border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800/50 hover:border-gray-600'}">
								<div class="font-medium text-sm">⚡ TRC20 USDT (TRON)</div>
								<div class="text-xs text-gray-500 mt-1">Send ${currentPrice} USDT to: <strong class="text-gray-700 dark:text-gray-300 cursor-pointer font-mono text-[11px]" on:click|stopPropagation={() => copyAddress(paymentInfo.trc20_address)}>{paymentInfo.trc20_address?.slice(0, 10)}...{paymentInfo.trc20_address?.slice(-6)}</strong></div>
							</button>
						{/if}
					</div>

					{#if paymentMethod}
						<div class="mb-4">
							<label class="text-xs text-gray-600 dark:text-gray-400 mb-1 block">Transaction Hash / Payment ID</label>
							<input bind:value={txHash} placeholder="Paste your transaction hash after sending"
								class="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-100 dark:bg-gray-800 px-3 py-2 text-sm font-mono" />
						</div>
						<button on:click={subscribe} disabled={subscribing || !txHash}
							class="w-full py-2.5 bg-orange-600 text-gray-900 dark:text-white rounded-xl font-medium hover:bg-orange-700 transition disabled:opacity-50">
							{subscribing ? 'Verifying...' : 'Verify Payment & Subscribe'}
						</button>
					{/if}
				{/if}

				<button on:click={() => { showPayment = false; selectedPkg = ''; }}
					class="w-full mt-3 py-2 text-sm text-gray-500 hover:text-gray-300 transition">Cancel</button>
			</div>
		{/if}
		{/if}
	</div>
</div>
