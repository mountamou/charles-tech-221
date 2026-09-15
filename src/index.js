import { Container, getContainer } from "@cloudflare/containers";
import { env } from "cloudflare:workers";

const PRIMARY_HOST = "www.charlestech221.com";
const APEX_HOST = "charlestech221.com";

// Undefined values (e.g. a secret not set yet) are left out instead of reaching the container.
const defined = (vars) => Object.fromEntries(Object.entries(vars).filter(([, value]) => value !== undefined));

export class Backend extends Container {
	defaultPort = 8000; // matches serve.py (uvicorn on $PORT, default 8000)
	sleepAfter = "10m";
	envVars = defined({
		ENVIRONMENT: env.ENVIRONMENT,
		ADMIN_EMAIL: env.ADMIN_EMAIL,
		EMPLOYEE_EMAIL: env.EMPLOYEE_EMAIL,
		CONTACT_PHONE: env.CONTACT_PHONE,
		CONTACT_EMAIL: env.CONTACT_EMAIL,
		COMPANY_NAME: env.COMPANY_NAME,
		COMPANY_ADDRESS: env.COMPANY_ADDRESS,
		CURRENCY: env.CURRENCY,
		WAVE_MERCHANT_NUMBER: env.WAVE_MERCHANT_NUMBER,
		ORANGE_MONEY_NUMBER: env.ORANGE_MONEY_NUMBER,
		R2_ACCOUNT_ID: env.R2_ACCOUNT_ID,
		R2_BUCKET: env.R2_BUCKET,
		// Secrets (set via `wrangler secret put NAME` or the dashboard), forwarded as-is.
		// The SQLite database path is fixed in the Dockerfile and replicated to R2 by Litestream.
		SECRET_KEY: env.SECRET_KEY,
		ADMIN_PASSWORD: env.ADMIN_PASSWORD,
		EMPLOYEE_PASSWORD: env.EMPLOYEE_PASSWORD,
		R2_ACCESS_KEY_ID: env.R2_ACCESS_KEY_ID,
		R2_SECRET_ACCESS_KEY: env.R2_SECRET_ACCESS_KEY,
	});
};

export default {
	async fetch(request, env) {
		const url = new URL(request.url);
		if (url.hostname === APEX_HOST) {
			url.hostname = PRIMARY_HOST;
			return Response.redirect(url.toString(), 301);
		}
		const container = getContainer(env.BACKEND);
		return container.fetch(request);
	},
};
