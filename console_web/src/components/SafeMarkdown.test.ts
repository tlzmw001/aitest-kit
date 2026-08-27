// @vitest-environment jsdom

import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SafeMarkdown from './SafeMarkdown.vue'

describe('SafeMarkdown', () => {
  it('renders report structure and keeps safe links', () => {
    const wrapper = mount(SafeMarkdown, {
      props: {
        source: [
          '# Run report',
          '',
          '- passed: 3',
          '',
          '| case | status |',
          '| --- | --- |',
          '| TC-001 | passed |',
          '',
          '```json',
          '{"status":"passed"}',
          '```',
          '',
          '[details](https://example.com/report)',
        ].join('\n'),
      },
    })

    expect(wrapper.get('h1').text()).toBe('Run report')
    expect(wrapper.get('table').text()).toContain('TC-001')
    expect(wrapper.get('code.language-json').text()).toContain('passed')
    expect(wrapper.get('a').attributes()).toMatchObject({
      href: 'https://example.com/report',
      target: '_blank',
      rel: 'noopener noreferrer',
    })
  })

  it('removes raw HTML, images, event handlers and unsafe URLs', () => {
    const wrapper = mount(SafeMarkdown, {
      props: {
        source: [
          '<script>window.__markdownExecuted = true</script>',
          '<img src="https://example.com/pixel" onerror="window.__imageExecuted = true">',
          '[unsafe](javascript:alert(1))',
          '![tracking](https://example.com/tracker.png)',
          '<div onclick="alert(1)">raw html</div>',
        ].join('\n\n'),
      },
    })

    expect(wrapper.find('script').exists()).toBe(false)
    expect(wrapper.find('img').exists()).toBe(false)
    expect(wrapper.find('[onerror]').exists()).toBe(false)
    expect(wrapper.find('[onclick]').exists()).toBe(false)
    expect(wrapper.find('a[href^="javascript:"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('unsafe')
  })

  it('shows the supplied empty state for an empty report', () => {
    const wrapper = mount(SafeMarkdown, {
      props: { source: '', emptyText: '本次执行没有 report.md。' },
    })

    expect(wrapper.get('[data-test="markdown-empty"]').text()).toBe('本次执行没有 report.md。')
  })
})
