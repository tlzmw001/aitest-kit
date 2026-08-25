import { describe, expect, it } from 'vitest'
import { displayOwner, ownerLabel } from './classification'

describe('failure ownership', () => {
  it('keeps assertion failures in review instead of blaming the SUT', () => {
    expect(displayOwner('ASSERTION_FAILURE')).toBe('REVIEW')
    expect(ownerLabel('REVIEW')).toBe('待确认')
  })

  it('maps environment, scaffold, cleanup and config evidence', () => {
    expect(displayOwner('PRECONDITION_MISSING')).toBe('ENV')
    expect(displayOwner('TEST_SCAFFOLD_ERROR')).toBe('SCAFFOLD')
    expect(displayOwner('TEARDOWN_ERROR')).toBe('CLEANUP')
    expect(displayOwner('E504')).toBe('CONFIG')
  })
})
