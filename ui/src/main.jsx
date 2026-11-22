import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Toaster } from 'sonner'
import './index.css'
import '@fontsource-variable/instrument-sans'
import '@fontsource/ibm-plex-mono/latin-500.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
    <Toaster className="payscope-toasts" position="bottom-right" closeButton />
  </StrictMode>,
)
