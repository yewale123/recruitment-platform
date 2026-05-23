import { useState } from 'react'

const PLATFORMS = [
  { id: 'linkedin', label: 'LinkedIn' },
  { id: 'github',   label: 'GitHub' },
]

function TagInput({ tags, onChange, placeholder }) {
  const [input, setInput] = useState('')

  function addTag(val) {
    const trimmed = val.trim()
    if (trimmed && !tags.includes(trimmed)) {
      onChange([...tags, trimmed])
    }
    setInput('')
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      addTag(input)
    } else if (e.key === 'Backspace' && !input && tags.length) {
      onChange(tags.slice(0, -1))
    }
  }

  function removeTag(tag) {
    onChange(tags.filter(t => t !== tag))
  }

  return (
    <div className="tags-container" onClick={() => document.getElementById('ti-' + placeholder)?.focus()}>
      {tags.map(tag => (
        <span key={tag} className="tag">
          {tag}
          <button type="button" className="tag-remove" onClick={() => removeTag(tag)}>×</button>
        </span>
      ))}
      <input
        id={'ti-' + placeholder}
        className="tags-input"
        value={input}
        placeholder={tags.length ? '' : placeholder}
        onChange={e => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={() => addTag(input)}
      />
    </div>
  )
}

export default function RequestForm({ onSubmit, isSubmitting }) {
  const [form, setForm] = useState({
    title: '',
    required_skills: [],
    experience_min: 0,
    experience_max: '',
    location: '',
    isRemote: false,
    keywords: [],
    platforms: ['linkedin'],
  })
  const [errors, setErrors] = useState({})

  function validate() {
    const e = {}
    if (!form.title.trim()) e.title = 'Job title is required'
    if (!form.required_skills.length) e.required_skills = 'Add at least one required skill'
    if (!form.platforms.length) e.platforms = 'Select at least one platform'
    setErrors(e)
    return Object.keys(e).length === 0
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (!validate()) return

    const payload = {
      title: form.title.trim(),
      required_skills: form.required_skills,
      experience_min: Number(form.experience_min) || 0,
      experience_max: form.experience_max ? Number(form.experience_max) : null,
      location: form.isRemote ? 'Remote' : (form.location.trim() || null),
      keywords: form.keywords,
      platforms: form.platforms,
    }
    onSubmit(payload)
  }

  function togglePlatform(platform) {
    setForm(f => ({
      ...f,
      platforms: f.platforms.includes(platform)
        ? f.platforms.filter(p => p !== platform)
        : [...f.platforms, platform],
    }))
  }

  return (
    <form onSubmit={handleSubmit} noValidate>
      <div className="form-group">
        <label className="form-label">Job Title *</label>
        <input
          className="form-input"
          placeholder="e.g. Senior Python Developer"
          value={form.title}
          onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
        />
        {errors.title && <span className="text-sm" style={{ color: 'var(--danger)' }}>{errors.title}</span>}
      </div>

      <div className="form-group">
        <label className="form-label">Required Skills *</label>
        <TagInput
          tags={form.required_skills}
          onChange={v => setForm(f => ({ ...f, required_skills: v }))}
          placeholder="Type a skill and press Enter"
        />
        {errors.required_skills && <span className="text-sm" style={{ color: 'var(--danger)' }}>{errors.required_skills}</span>}
        <span className="form-hint">e.g. Python, FastAPI, MySQL</span>
      </div>

      <div className="form-row">
        <div className="form-group">
          <label className="form-label">Min Experience (years)</label>
          <input
            type="number" className="form-input" min="0" max="50"
            value={form.experience_min}
            onChange={e => setForm(f => ({ ...f, experience_min: e.target.value }))}
          />
        </div>
        <div className="form-group">
          <label className="form-label">Max Experience (years)</label>
          <input
            type="number" className="form-input" min="0" max="50"
            placeholder="Leave blank for no limit"
            value={form.experience_max}
            onChange={e => setForm(f => ({ ...f, experience_max: e.target.value }))}
          />
        </div>
      </div>

      <div className="form-group">
        <label className="form-label">Location</label>
        <input
          className="form-input"
          placeholder="e.g. Bangalore, Mumbai, Delhi"
          value={form.isRemote ? '' : form.location}
          disabled={form.isRemote}
          onChange={e => setForm(f => ({ ...f, location: e.target.value }))}
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: '.4rem', marginTop: '.4rem', fontSize: '.875rem', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={form.isRemote}
            onChange={e => setForm(f => ({ ...f, isRemote: e.target.checked, location: '' }))}
          />
          Remote (any location)
        </label>
      </div>

      <div className="form-group">
        <label className="form-label">Keywords <span className="text-muted">(optional)</span></label>
        <TagInput
          tags={form.keywords}
          onChange={v => setForm(f => ({ ...f, keywords: v }))}
          placeholder="e.g. microservices, REST API, startup"
        />
        <span className="form-hint">Extra terms to match in candidate headline / summary</span>
      </div>

      <div className="form-group">
        <label className="form-label">Platforms *</label>
        <div className="flex gap-4 mt-1">
          {PLATFORMS.map(({ id, label }) => (
            <label key={id} style={{ display: 'flex', alignItems: 'center', gap: '.4rem', cursor: 'pointer', fontSize: '.875rem' }}>
              <input
                type="checkbox"
                checked={form.platforms.includes(id)}
                onChange={() => togglePlatform(id)}
              />
              {label}
            </label>
          ))}
        </div>
        {errors.platforms && <span className="text-sm" style={{ color: 'var(--danger)' }}>{errors.platforms}</span>}
      </div>

      <button type="submit" className="btn btn-primary" disabled={isSubmitting} style={{ width: '100%', justifyContent: 'center', padding: '.75rem' }}>
        {isSubmitting ? <><span className="spinner" style={{ width: 16, height: 16 }} /> Submitting...</> : 'Submit Recruitment Request'}
      </button>
    </form>
  )
}
