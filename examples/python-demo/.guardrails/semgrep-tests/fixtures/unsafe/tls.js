const https = require("https");

// ruleid: guardrails.javascript-disabled-tls-verification
new https.Agent({ rejectUnauthorized: false });
