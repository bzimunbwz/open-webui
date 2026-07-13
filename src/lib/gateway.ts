// Single source of truth for the facade gateway base URL.
//
// The gateway runs as its own service. Change DEFAULT_GATEWAY_URL below when the
// gateway moves host (e.g. to https://gateway.claudesk.pro on a self-hosted
// deploy). Any browser can also point the app at a different gateway by setting
// localStorage 'gateway_url' — the admin Providers page writes this key.
const DEFAULT_GATEWAY_URL = 'https://webapp-2nd-service-production.up.railway.app';

export const getGatewayUrl = (): string => {
	try {
		if (typeof localStorage !== 'undefined') {
			const override = (localStorage.getItem('gateway_url') || '').trim();
			if (override) {
				const url = /^https?:\/\//.test(override) ? override : `https://${override}`;
				return url.replace(/\/+$/, '');
			}
		}
	} catch (e) {
		// localStorage can throw in private mode / SSR — fall through to default
	}
	return DEFAULT_GATEWAY_URL;
};

export { DEFAULT_GATEWAY_URL };
