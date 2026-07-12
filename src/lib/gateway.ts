// Single source of truth for the facade gateway base URL.
//
// The gateway runs as its own service. In production it is served at
// https://gateway.claudesk.pro (see Caddyfile). Any browser can point the app
// at a different gateway by setting localStorage 'gateway_url' — the admin
// Providers page writes this key.
const DEFAULT_GATEWAY_URL = 'https://gateway.claudesk.pro';

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
