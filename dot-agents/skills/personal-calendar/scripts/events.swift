// Usage: swift events.swift START END [QUERY]
// START/END are ISO 8601 (2026-11-24T00:00:00-08:00). Prints events from the
// iCloud calendars only (Bryan, Family, Traci, ...), never the Google ones.
import EventKit
import Foundation

let args = CommandLine.arguments
guard args.count >= 3, let start = ISO8601DateFormatter().date(from: args[1]),
      let end = ISO8601DateFormatter().date(from: args[2]) else {
    FileHandle.standardError.write("usage: events.swift START END [QUERY]\n".data(using: .utf8)!)
    exit(2)
}
let query = args.count > 3 ? args[3].lowercased() : nil
let store = EKEventStore()
let done = DispatchSemaphore(value: 0)
store.requestFullAccessToEvents { granted, error in
    guard granted else { print("calendar access denied: \(String(describing: error))"); exit(1) }
    let cals = store.calendars(for: .event).filter { $0.source.title == "iCloud" }
    let out = DateFormatter()
    out.dateFormat = "yyyy-MM-dd HH:mm zzz"
    out.timeZone = TimeZone(identifier: "America/Los_Angeles")
    for e in store.events(matching: store.predicateForEvents(withStart: start, end: end, calendars: cals)) {
        let text = [e.title, e.location, e.notes].compactMap { $0 }.joined(separator: " ")
        if let q = query, !text.lowercased().contains(q) { continue }
        print("[\(e.calendar.title)] \(e.title ?? "") | \(out.string(from: e.startDate)) -> \(out.string(from: e.endDate)) | \(e.location ?? "")")
        if let n = e.notes, !n.isEmpty { print("  " + n.prefix(400).replacingOccurrences(of: "\n", with: "\n  ")) }
    }
    done.signal()
}
done.wait()
