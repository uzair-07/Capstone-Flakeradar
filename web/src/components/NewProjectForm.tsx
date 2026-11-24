import { useState, type FormEvent } from 'react'
import { api, ApiError, type Project } from '../api'

export function NewProjectForm({ onCreated }: { onCreated: (project: Project) => void }) {
  const [name, setName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      onCreated(await api.createProject(name.trim()))
      setName('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not create the project.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit} className="inline-form">
      <label htmlFor="project-name">Project name</label>
      <input
        id="project-name"
        required
        maxLength={100}
        placeholder="e.g. Checkout service"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <button type="submit" className="primary" disabled={busy || !name.trim()}>
        Create project
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
