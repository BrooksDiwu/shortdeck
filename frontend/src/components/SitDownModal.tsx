import { useState } from 'react'
import Modal from './Modal'

interface SitDownModalProps {
  open: boolean
  seat: number | null
  onConfirm: (seat: number, chips: number) => void
  onClose: () => void
}

export default function SitDownModal({ open, seat, onConfirm, onClose }: SitDownModalProps) {
  const [chips, setChips] = useState(1000)

  const handleConfirm = () => {
    if (seat === null) return
    onConfirm(seat, chips)
    onClose()
  }

  return (
    <Modal open={open} onClose={onClose} title={`Take Seat ${seat}`}>
      <div className="flex flex-col gap-4">
        <p className="text-zinc-400 text-sm">
          How many chips would you like to bring to the table?
        </p>

        <div className="flex flex-col gap-1">
          <label className="text-zinc-400 text-xs font-medium">Starting Chips</label>
          <input
            type="number"
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-green-500"
            value={chips}
            min={1}
            onChange={(e) => setChips(Number(e.target.value))}
          />
        </div>

        {/* Quick selects */}
        <div className="grid grid-cols-4 gap-2">
          {[500, 1000, 2000, 5000].map((v) => (
            <button
              key={v}
              onClick={() => setChips(v)}
              className={`py-2 rounded-lg text-sm font-medium transition-colors ${
                chips === v
                  ? 'bg-green-600 text-white'
                  : 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
              }`}
            >
              {v.toLocaleString()}
            </button>
          ))}
        </div>

        <div className="flex gap-3 pt-2">
          <button
            className="flex-1 py-2.5 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-white text-sm transition-colors"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 rounded-xl text-white font-semibold text-sm transition-colors"
            onClick={handleConfirm}
          >
            Request Seat
          </button>
        </div>

        <p className="text-zinc-600 text-xs text-center">
          Your request will be sent to the host for approval.
        </p>
      </div>
    </Modal>
  )
}
