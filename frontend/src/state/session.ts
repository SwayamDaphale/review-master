export interface Session {
  provider: 'google' | 'demo';
  sub: string;
  email: string;
  name: string;
  picture?: string;
  signedInAt: string;
}
