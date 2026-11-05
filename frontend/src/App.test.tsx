import { describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import App from './App';
import { renderWithProviders } from './test/utils';
import { ADMIN_PASSWORD } from './lib/adminAuth';
import { STORAGE_KEYS, writeStored } from './lib/storage';

vi.mock('./auth/google', async (importOriginal) => {
  const original = await importOriginal<typeof import('./auth/google')>();
  return { ...original, isGoogleConfigured: () => false };
});

describe('public site', () => {
  it('shows the landing page headline', async () => {
    renderWithProviders(<App />, '/');
    expect(await screen.findByRole('heading', { level: 1, name: /Stop trusting fake 5-star reviews/ })).toBeInTheDocument();
  });

  it('toggles between light and dark mode', async () => {
    renderWithProviders(<App />, '/');
    const btn = await screen.findByRole('button', { name: /switch to (dark|light) mode/i });
    const before = document.documentElement.getAttribute('data-theme');
    fireEvent.click(btn);
    await waitFor(() => expect(document.documentElement.getAttribute('data-theme')).not.toBe(before));
  });
});

describe('app pages', () => {
  it('shows the score, confidence and an AI-labelled summary for a product', async () => {
    renderWithProviders(<App />, '/app/products/p-galaxy-s25-ultra?v=v-s25u-12-256');
    expect(await screen.findByRole('heading', { level: 1, name: 'Samsung Galaxy S25 Ultra' })).toBeInTheDocument();
    expect(await screen.findAllByText('Limited confidence')).not.toHaveLength(0);
    expect(screen.getAllByText('AI grounded summary').length).toBeGreaterThan(0);
  });

  it('withholds the score when evidence is insufficient', async () => {
    renderWithProviders(<App />, '/app/products/p-sample-phone-c?v=v-phone-c-8-128');
    expect(await screen.findByText(/withheld because there is not enough evidence/i)).toBeInTheDocument();
    expect(screen.getAllByText('Not scored').length).toBeGreaterThan(0);
  });

  it('blocks a cross-category comparison with a clear message', async () => {
    renderWithProviders(<App />, '/app/compare?ids=v-s25u-12-256,v-ssd-1tb');
    expect(await screen.findByText(/different categories/i)).toBeInTheDocument();
  });

  it('sends a signed-out visitor to sign in before Saved', async () => {
    renderWithProviders(<App />, '/app/saved');
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('offers a demo account when Google sign-in is not configured', async () => {
    renderWithProviders(<App />, '/login');
    const demo = await screen.findByRole('button', { name: /continue with a demo account/i });
    fireEvent.click(demo);
    expect(await screen.findByRole('heading', { level: 1, name: /What are you thinking of buying/ })).toBeInTheDocument();
  });

  it('shows what an import captured and what it did not', async () => {
    renderWithProviders(<App />, '/app/import');
    fireEvent.click(await screen.findByRole('button', { name: /iPhone sample/i }));
    expect(await screen.findByText(/Probable match/)).toBeInTheDocument();
    expect(screen.getAllByText('Not captured').length).toBeGreaterThan(0);
  });
});

describe('admin', () => {
  it('rejects a wrong password and accepts the right one', async () => {
    renderWithProviders(<App />, '/admin');
    const input = await screen.findByLabelText('Password');
    fireEvent.change(input, { target: { value: 'definitely-wrong' } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/not correct/i);

    fireEvent.change(screen.getByLabelText('Password'), { target: { value: ADMIN_PASSWORD } });
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Overview' })).toBeInTheDocument();
  });

  it('keeps Publish disabled until a model meets the rules', async () => {
    writeStored(STORAGE_KEYS.adminSession, { expiresAt: new Date(Date.now() + 3_600_000).toISOString() });
    renderWithProviders(<App />, '/admin/models');
    const buttons = await screen.findAllByRole('button', { name: 'Publish this version' });
    expect(buttons).toHaveLength(3);
    buttons.forEach((b) => expect(b).toBeDisabled());
    expect(screen.getAllByText(/weights are not set/).length).toBe(3);
  });
});
