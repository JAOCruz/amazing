/**
 * Generic DGII e-CF XML signing script.
 * Imports ONLY signing modules (no networking/axios/undici) to avoid
 * WebAssembly memory issues in constrained Docker containers.
 *
 * Usage: node sign_generic.mjs <input.xml> <output.xml> <p12file> <password> <rootElName>
 */
import { createRequire } from 'module';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

// Import only what we need — skip networking modules that pull in undici/WebAssembly
const P12Reader = require(`${__dirname}/node_modules/dgii-ecf/dist/P12Reader.js`).default;
const Signature = require(`${__dirname}/node_modules/dgii-ecf/dist/Signature/Signature.js`).default;

const [,, inputFile, outputFile, p12File, password, rootElName] = process.argv;

if (!inputFile || !outputFile || !p12File || !password || !rootElName) {
  process.stderr.write('Usage: node sign_generic.mjs <input.xml> <output.xml> <p12file> <password> <rootElName>\n');
  process.exit(1);
}

const reader = new P12Reader(password);
const certs = reader.getKeyFromFile(p12File);

if (!certs.key || !certs.cert) {
  process.stderr.write('❌ Failed to read certificate\n');
  process.exit(1);
}

const xml = readFileSync(inputFile, 'utf-8');
const signature = new Signature(certs.key, certs.cert);
const signedXml = signature.signXml(xml, rootElName);

writeFileSync(outputFile, signedXml, 'utf-8');
process.stdout.write(`✅ Signed ${rootElName} → ${outputFile}\n`);
process.exit(0);
