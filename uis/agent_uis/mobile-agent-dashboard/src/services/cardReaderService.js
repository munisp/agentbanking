import NfcManager, { NfcTech } from "react-native-nfc-manager";

let nfcInitialized = false;

// ── EMV APDU helpers ──────────────────────────────────────────────────────────

function selectAPDU(aid) {
  return [0x00, 0xa4, 0x04, 0x00, aid.length, ...aid, 0x00];
}

function readRecordAPDU(recNo, sfi) {
  return [0x00, 0xb2, recNo, (sfi << 3) | 0x04, 0x00];
}

const PPSE_AID = [
  0x32, 0x50, 0x41, 0x59, 0x2e, 0x53, 0x59, 0x53, 0x2e,
  0x44, 0x44, 0x46, 0x30, 0x31,
];

// Well-known payment AIDs tried in order if PPSE parse fails
const FALLBACK_AIDS = [
  [0xa0, 0x00, 0x00, 0x00, 0x03, 0x10, 0x10], // Visa
  [0xa0, 0x00, 0x00, 0x00, 0x04, 0x10, 0x10], // Mastercard
  [0xa0, 0x00, 0x00, 0x03, 0x71, 0x00, 0x01], // Verve
  [0xa0, 0x00, 0x00, 0x00, 0x65, 0x10, 0x10], // JCB
];

// ── TLV byte-scan helpers ─────────────────────────────────────────────────────

function findTag1(bytes, tag) {
  for (let i = 0; i < bytes.length - 1; i++) {
    if (bytes[i] === tag) {
      const len = bytes[i + 1];
      if (len > 0 && i + 2 + len <= bytes.length) {
        return bytes.slice(i + 2, i + 2 + len);
      }
    }
  }
  return null;
}

function findTag2(bytes, t1, t2) {
  for (let i = 0; i < bytes.length - 2; i++) {
    if (bytes[i] === t1 && bytes[i + 1] === t2) {
      const len = bytes[i + 2];
      if (len > 0 && i + 3 + len <= bytes.length) {
        return bytes.slice(i + 3, i + 3 + len);
      }
    }
  }
  return null;
}

function isSuccess(resp) {
  return (
    resp.length >= 2 &&
    resp[resp.length - 2] === 0x90 &&
    resp[resp.length - 1] === 0x00
  );
}

// ── Card data parsers ─────────────────────────────────────────────────────────

function parsePAN(panBytes) {
  const hex = Array.from(panBytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase()
    .replace(/F+$/, ""); // strip padding nibbles
  return hex;
}

function parseExpiry(expiryBytes) {
  // Stored as YYMMDD (packed BCD)
  const hex = Array.from(expiryBytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const yy = hex.substring(0, 2);
  const mm = hex.substring(2, 4);
  return `${mm} / ${yy}`;
}

function detectProvider(pan) {
  const d = pan.replace(/\s/g, "");
  if (d.startsWith("4")) return "Visa";
  if (d.startsWith("50") || d.startsWith("65") || d.startsWith("6")) return "Verve";
  if (d.startsWith("5")) return "Mastercard";
  if (d.startsWith("3")) return "Amex";
  return "";
}

// ── Core EMV read ─────────────────────────────────────────────────────────────

async function readEMV(isoDep) {
  // 1. SELECT PPSE
  let resp = await isoDep.transceive(selectAPDU(PPSE_AID));

  let aid = null;
  if (isSuccess(resp)) {
    // Try to find AID (tag 4F) in PPSE response
    const aidBytes = findTag1(resp, 0x4f);
    if (aidBytes && aidBytes.length >= 5) {
      aid = Array.from(aidBytes);
    }
  }

  // 2. If PPSE didn't give an AID, probe fallback AIDs
  if (!aid) {
    for (const candidate of FALLBACK_AIDS) {
      const r = await isoDep.transceive(selectAPDU(candidate));
      if (isSuccess(r)) {
        aid = candidate;
        break;
      }
    }
  }

  if (!aid) throw new Error("No payment application found on this card.");

  // 3. SELECT the application
  resp = await isoDep.transceive(selectAPDU(aid));
  if (!isSuccess(resp)) throw new Error("Could not select payment application.");

  // 4. Scan SFI 1-3, records 1-8 looking for PAN (5A) and expiry (5F24)
  let pan = null;
  let expiry = null;

  for (let sfi = 1; sfi <= 3; sfi++) {
    for (let rec = 1; rec <= 8; rec++) {
      try {
        const recResp = await isoDep.transceive(readRecordAPDU(rec, sfi));
        if (!isSuccess(recResp)) continue;

        if (!pan) {
          const panBytes = findTag1(recResp, 0x5a);
          if (panBytes) pan = parsePAN(panBytes);
        }
        if (!expiry) {
          const expBytes = findTag2(recResp, 0x5f, 0x24);
          if (expBytes) expiry = parseExpiry(expBytes);
        }

        if (pan && expiry) break;
      } catch {
        // Record doesn't exist at this SFI/rec — continue
      }
    }
    if (pan && expiry) break;
  }

  if (!pan) throw new Error("Could not read card number. Please enter manually.");

  return {
    cardNumber: pan,
    expiryDate: expiry || "",
    cardProvider: detectProvider(pan),
  };
}

// ── Public API ────────────────────────────────────────────────────────────────

export async function isNfcSupported() {
  try {
    return await NfcManager.isSupported();
  } catch {
    return false;
  }
}

export async function initNfc() {
  if (nfcInitialized) return true;
  const supported = await NfcManager.isSupported();
  if (!supported) return false;
  await NfcManager.start();
  nfcInitialized = true;
  return true;
}

export async function readCardNFC() {
  await initNfc();

  try {
    await NfcManager.requestTechnology(NfcTech.IsoDep, {
      alertMessage: "Hold your card flat against the back of your phone",
    });
    return await readEMV(NfcManager.isoDepHandler);
  } finally {
    NfcManager.cancelTechnologyRequest().catch(() => {});
  }
}

export function cancelNfcRead() {
  NfcManager.cancelTechnologyRequest().catch(() => {});
}
