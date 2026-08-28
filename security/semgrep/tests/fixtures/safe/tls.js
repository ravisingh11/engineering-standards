const https = require("https");

// ok: guardrails.javascript-disabled-tls-verification
new https.Agent({ rejectUnauthorized: true });
