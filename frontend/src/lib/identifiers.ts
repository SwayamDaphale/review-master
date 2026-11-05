export type ParsedIdentifier =
  | { kind: 'asin'; asin: string; value: string }
  | { kind: 'url'; asin: string | null; host: string; value: string }
  | { kind: 'text'; value: string };

const ASIN_IN_PATH = /(?:\/dp\/|\/gp\/product\/|\/product\/)([A-Z0-9]{10})(?=[/?#]|$)/i;

/** Decides whether the search box holds an Amazon link, an ASIN, or plain words. */
export function parseIdentifier(input: string): ParsedIdentifier {
  const value = input.trim();
  if (/^B0[A-Z0-9]{8}$/i.test(value)) {
    return { kind: 'asin', asin: value.toUpperCase(), value };
  }
  if (/^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value);
      const match = ASIN_IN_PATH.exec(url.pathname);
      return {
        kind: 'url',
        asin: match?.[1] ? match[1].toUpperCase() : null,
        host: url.hostname,
        value,
      };
    } catch {
      return { kind: 'text', value };
    }
  }
  return { kind: 'text', value };
}
