// Written by kmctl plugin patch; it rewrites this file. kmctl plugin patch
// --undo deletes it. It adds kmctl's knowledge briefing to each session and
// never fails one: without a working kmctl it adds nothing.
import { execFile } from "node:child_process"

const briefing = (cwd) =>
  new Promise((resolve) => {
    try {
      execFile(
        "kmctl",
        ["briefing", "--path", cwd],
        { cwd, timeout: 10000, windowsHide: true },
        (error, stdout) => resolve(error ? "" : String(stdout).trim()),
      )
    } catch {
      resolve("")
    }
  })

const said = async (text) => {
  try {
    return await text
  } catch {
    return ""
  }
}

export default {
  id: "kmctl",
  setup: async (ctx) => {
    try {
      const where = ctx?.location
      const text = briefing(where?.project?.directory ?? where?.directory ?? process.cwd())
      await ctx.session.hook("context", async (event) => {
        try {
          const out = await said(text)
          if (out) event.system.push({ type: "text", text: out })
        } catch {}
      })
    } catch {}
  },
}
