export interface Session {
  provider: 'local' | 'google' | 'demo';
  sub: string;
  email: string;
  name: string;
  picture?: string;
  signedInAt: string;
  accessToken?: string;
  roles?: string[];
}
