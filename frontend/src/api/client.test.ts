import { describe, expect, it, vi } from 'vitest'
import { apiFetch, ApiError } from './client'

describe('apiFetch error handling', () => {
  it('formats a FastAPI/Pydantic 422 validation error list into a readable message', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [
            {
              type: 'value_error',
              loc: ['body', 'email'],
              msg: 'value is not a valid email address: An email address must have an @-sign.',
              input: '10101010',
            },
            {
              type: 'string_too_short',
              loc: ['body', 'password'],
              msg: 'String should have at least 8 characters',
              input: '',
            },
          ],
        }),
        { status: 422, headers: { 'Content-Type': 'application/json' } },
      ),
    )

    await expect(apiFetch('/auth/login')).rejects.toMatchObject({
      status: 422,
      message: expect.stringMatching(
        /email: value is not a valid email address.*password: String should have at least 8 characters/,
      ),
    })
  })

  it('keeps a plain string detail as-is', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Credenciales invalidas' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    await expect(apiFetch('/auth/login')).rejects.toThrow('Credenciales invalidas')
  })

  it('falls back to statusText when the body is not JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('not json', { status: 500, statusText: 'Internal Server Error' }),
    )

    await expect(apiFetch('/auth/login')).rejects.toThrow('Internal Server Error')
  })

  it('throws an ApiError instance carrying the status code', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'not found' }), { status: 404 }),
    )

    try {
      await apiFetch('/auth/login')
      throw new Error('expected apiFetch to reject')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      expect((error as ApiError).status).toBe(404)
    }
  })
})
