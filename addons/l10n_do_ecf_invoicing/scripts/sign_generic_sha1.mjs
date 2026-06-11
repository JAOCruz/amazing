/**
 * DGII e-CF XML signing script using SHA-1 (required by DGII TesteCF).
 *
 * The dgii-ecf package v1.8.0 defaults to SHA-256, but DGII TesteCF
 * rejects signatures that don't use SHA-1.
 *
 * This script:
 * 1. For ECF documents: sorts namespace attributes alphabetically
 *    (the critical DGII hack) before signing
 * 2. Signs using xml-crypto with SHA-1 for both signature and digest
 *
 * Usage: node sign_generic_sha1.mjs <input.xml> <output.xml> <p12file> <password> <rootElName>
 */
import { createRequire } from 'module';
import { readFileSync, writeFileSync } from 'fs';
import { dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

const P12Reader = require(`${__dirname}/node_modules/dgii-ecf/dist/P12Reader.js`).default;
const { SignedXml } = require(`${__dirname}/node_modules/xml-crypto`);
const { DOMParser, XMLSerializer } = require(`${__dirname}/node_modules/@xmldom/xmldom`);

const [,, inputFile, outputFile, p12File, password, rootElName] = process.argv;

if (!inputFile || !outputFile || !p12File || !password || !rootElName) {
  process.stderr.write('Usage: node sign_generic_sha1.mjs <input.xml> <output.xml> <p12file> <password> <rootElName>\n');
  process.exit(1);
}

const reader = new P12Reader(password);
const certs = reader.getKeyFromFile(p12File);

if (!certs.key || !certs.cert) {
  process.stderr.write('❌ Failed to read certificate\n');
  process.exit(1);
}

const xml = readFileSync(inputFile, 'utf-8');

// --- DGII Namespace Sorting Hack ---
// Only apply to ECF documents, NOT to SemillaModel (authentication seed)
// DGII requires namespace attributes to be sorted alphabetically
// before computing the digest. Without this, the digest won't match.
function sortNamespaces(xmlString) {
  const doc = new DOMParser().parseFromString(xmlString, 'text/xml');
  const root = doc.documentElement;

  // Sort attributes alphabetically by name
  const attrs = Array.from(root.attributes);
  attrs.sort((a, b) => a.name.localeCompare(b.name));

  // Remove all attributes and re-add in sorted order
  while (root.attributes.length > 0) {
    root.removeAttribute(root.attributes[0].name);
  }
  for (const attr of attrs) {
    root.setAttribute(attr.name, attr.value);
  }

  return new XMLSerializer().serializeToString(doc);
}

// Only sort namespaces for ECF, not for SemillaModel
const xmlToSign = rootElName === 'ECF' ? sortNamespaces(xml) : xml;

// --- Sign with SHA-1 ---
const sig = new SignedXml({
  privateKey: certs.key,
  publicCert: certs.cert,
  signatureAlgorithm: 'http://www.w3.org/2000/09/xmldsig#rsa-sha1',
  canonicalizationAlgorithm: 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
});

sig.addReference({
  xpath: `//*[local-name(.)='${rootElName}']`,
  transforms: ['http://www.w3.org/2000/09/xmldsig#enveloped-signature'],
  digestAlgorithm: 'http://www.w3.org/2000/09/xmldsig#sha1',
  isEmptyUri: true
});

sig.computeSignature(xmlToSign);
writeFileSync(outputFile, sig.getSignedXml(), 'utf-8');
process.stdout.write(`✅ Signed ${rootElName} with SHA-1 → ${outputFile}\n`);
process.exit(0);
