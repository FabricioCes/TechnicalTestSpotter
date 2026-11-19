import { useEffect, useId, useRef, useState } from 'react'
import { suggestAddresses } from '../api'

const DEBOUNCE_MS = 300
const MIN_CHARS = 3

// Text field with US address suggestions, similar to Google Maps.
// `onChange` receives { text, place }: place is set only after a suggestion is picked.
export default function AddressInput({ label, placeholder, value, onChange, required }) {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [status, setStatus] = useState('idle') // idle | loading | empty | error
  const [active, setActive] = useState(-1)
  const listId = useId()
  const wrapperRef = useRef(null)

  // Fetch suggestions after the user pauses typing. Stale requests are aborted.
  useEffect(() => {
    const query = value.text.trim()
    if (value.place || query.length < MIN_CHARS) {
      setItems([])
      setStatus('idle')
      return undefined
    }

    const controller = new AbortController()
    setStatus('loading')
    const timer = setTimeout(async () => {
      try {
        const results = await suggestAddresses(query, { signal: controller.signal })
        setItems(results)
        setActive(-1)
        setStatus(results.length ? 'ready' : 'empty')
        setOpen(true)
      } catch (err) {
        if (err.name !== 'AbortError') {
          setItems([])
          setStatus('error')
        }
      }
    }, DEBOUNCE_MS)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [value.text, value.place])

  // Close the list when the user clicks elsewhere.
  useEffect(() => {
    const handleClick = (event) => {
      if (!wrapperRef.current?.contains(event.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const choose = (place) => {
    onChange({ text: place.label, place })
    setOpen(false)
    setItems([])
    setStatus('idle')
  }

  const handleKeyDown = (event) => {
    if (!open || items.length === 0) return
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      setActive((i) => (i + 1) % items.length)
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      setActive((i) => (i <= 0 ? items.length - 1 : i - 1))
    } else if (event.key === 'Enter' && active >= 0) {
      event.preventDefault()
      choose(items[active])
    } else if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && (status === 'ready' || status === 'empty' || status === 'loading')
  const activeId = active >= 0 ? `${listId}-${active}` : undefined

  return (
    <div className="address-field" ref={wrapperRef}>
      <label>
        {label}
        <input
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={showList}
          aria-controls={listId}
          aria-activedescendant={activeId}
          autoComplete="off"
          required={required}
          placeholder={placeholder}
          value={value.text}
          onChange={(event) => {
            onChange({ text: event.target.value, place: null })
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
        />
      </label>

      {showList && (
        <ul id={listId} role="listbox" className="suggestions">
          {status === 'loading' && <li className="suggestion-note">Searching US addresses…</li>}
          {status === 'empty' && <li className="suggestion-note">No US addresses found</li>}
          {status === 'ready' &&
            items.map((place, index) => (
              <li
                key={`${place.label}-${index}`}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                className={index === active ? 'suggestion active' : 'suggestion'}
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(place)}
              >
                {place.label}
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}
