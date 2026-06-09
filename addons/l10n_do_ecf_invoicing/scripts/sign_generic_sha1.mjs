/**
 * DGII e-CF XML signing script using SHA-1 (required by DGII TesteCF).
 *
 * The dgii-ecf package v1.8.0 defaults to SHA-256, but DGII TesteCF
 * rejects signatures that don't use SHA-1.
 *
 * This script reuses dgii-ecf's P12Reader and custom Digest (with the
 * critical namespace attribute sorting hack), but overrides the
 * signature algorithm to SHA-1.
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
const { DOMParser } = require(`${__dirname}/node_modules/@xmldom/xmldom`);

// Import dgii-ecf's custom Digest which has the namespace sorting hack
const DigestModule = require(`${__dirname}/node_modules/dgii-ecf/dist/Signature/custom/Digest.js`);
const Digest = DigestModule.Digest || DigestModule.default;

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

// Create a custom Digest instance with SHA-1 instead of SHA-256
class DigestSha1 extends Digest {
  getHash(xml) {
    const crypto = require('crypto');
    const doc = new DOMParser().parseFromString(xml);
    const attrs = doc.childNodes[0].attributes;

    // Reuse parent's sort logic (the critical DGII hack)
    const items = this.sortElements ? this.sortElements(attrs) : Array.from(attrs).sort((a, b) => a < b ? -1 : a > b ? 1 : 0);
    Object.assign(doc.childNodes[0].attributes, items);

    // Use SHA-1 instead of SHA-256
    const shasum = crypto.createHash('sha1');
    shasum.update(doc.toString(), 'utf8');
    return shasum.digest('base64');
  }

  getAlgorithmName() {
    return 'http://www.w3.org/2000/09/xmldsig#sha1';
  }
}

const digestSha1 = new DigestSha1();

// DGII TesteCF requires SHA-1 for both signature and digest
const sig = new SignedXml({
  privateKey: certs.key,
  publicCert: certs.cert,
  signatureAlgorithm: 'http://www.w3.org/2000/09/xmldsig#rsa-sha1',
  canonicalizationAlgorithm: 'http://www.w3.org/TR/2001/REC-xml-c14n-20010315'
});

// Register our custom SHA-1 Digest with namespace sorting
sig.HashAlgorithms['http://myDigestAlgorithmSha1'] = digestSha1;

sig.addReference({
  xpath: `//*[local-name(.)='${rootElName}']`,
  transforms: ['http://www.w3.org/2000/09/xmldsig#enveloped-signature'],
  digestAlgorithm: 'http://myDigestAlgorithmSha1',
  isEmptyUri: true
});

sig.computeSignature(xml);
writeFileSync(outputFile, sig.getSignedXml(), 'utf-8');
process.stdout.write(`✅ Signed ${rootElName} with SHA-1 (DGII-compatible digest) → ${outputFile}\n`);
process.exit(0);
