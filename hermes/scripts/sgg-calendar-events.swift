import EventKit
import Foundation

struct CalendarEvent: Codable {
    let source: String
    let calendar: String
    let title: String
    let start: Date
    let end: Date
    let allDay: Bool
    let location: String?
    let url: String?
}

func truncate(_ value: String?, to limit: Int) -> String? {
    guard let value else { return nil }
    let cleaned = value.replacingOccurrences(of: "\u{0000}", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
    guard !cleaned.isEmpty else { return nil }
    return String(cleaned.prefix(limit))
}

let store = EKEventStore()
let semaphore = DispatchSemaphore(value: 0)
var granted = false
var requestError: Error?

switch EKEventStore.authorizationStatus(for: .event) {
case .fullAccess:
    granted = true
case .notDetermined:
    if #available(macOS 14.0, *) {
        store.requestFullAccessToEvents { allowed, error in
            granted = allowed
            requestError = error
            semaphore.signal()
        }
    } else {
        store.requestAccess(to: .event) { allowed, error in
            granted = allowed
            requestError = error
            semaphore.signal()
        }
    }
    _ = semaphore.wait(timeout: .now() + 120)
case .writeOnly, .restricted, .denied:
    granted = false
@unknown default:
    granted = false
}

if let requestError {
    FileHandle.standardError.write(Data("Calendar authorization error: \(requestError.localizedDescription)\n".utf8))
}

guard granted else {
    FileHandle.standardError.write(Data("Calendar access is not authorized.\n".utf8))
    exit(2)
}

let systemCalendar = Calendar.current
let start = systemCalendar.startOfDay(for: Date())
let end = systemCalendar.date(byAdding: .day, value: 1, to: start)!
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
let records = store.events(matching: predicate)
    .sorted { $0.startDate < $1.startDate }
    .map {
        CalendarEvent(
            source: "apple_calendar",
            calendar: $0.calendar.title,
            title: $0.title ?? "(untitled)",
            start: $0.startDate,
            end: $0.endDate,
            allDay: $0.isAllDay,
            location: truncate($0.location, to: 300),
            url: $0.url?.absoluteString
        )
    }

let encoder = JSONEncoder()
encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
encoder.dateEncodingStrategy = .iso8601
let data = try encoder.encode(records)
FileHandle.standardOutput.write(data)
FileHandle.standardOutput.write(Data("\n".utf8))
