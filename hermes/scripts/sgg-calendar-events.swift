import EventKit
import Foundation

struct ParticipantSummary: Codable {
    let name: String?
    let isCurrentUser: Bool
    let role: String
    let status: String
}

struct CalendarEvent: Codable {
    let eventIdentifier: String
    let occurrenceDate: Date?
    let source: String
    let calendar: String
    let title: String
    let start: Date
    let end: Date
    let allDay: Bool
    let location: String?
    let url: String?
    let organizer: ParticipantSummary?
    let currentUserAttendee: ParticipantSummary?
    let attendeeCount: Int
}

struct EventStatusResult: Codable {
    let status: String
    let reason: String
}

func truncate(_ value: String?, to limit: Int) -> String? {
    guard let value else { return nil }
    let cleaned = value.replacingOccurrences(of: "\u{0000}", with: "").trimmingCharacters(in: .whitespacesAndNewlines)
    guard !cleaned.isEmpty else { return nil }
    return String(cleaned.prefix(limit))
}

func participantRole(_ role: EKParticipantRole) -> String {
    switch role {
    case .required: return "required"
    case .optional: return "optional"
    case .chair: return "chair"
    case .nonParticipant: return "nonParticipant"
    case .unknown: return "unknown"
    @unknown default: return "unknown"
    }
}

func participantStatus(_ status: EKParticipantStatus) -> String {
    switch status {
    case .pending: return "pending"
    case .accepted: return "accepted"
    case .declined: return "declined"
    case .tentative: return "tentative"
    case .delegated: return "delegated"
    case .completed: return "completed"
    case .inProcess: return "inProcess"
    case .unknown: return "unknown"
    @unknown default: return "unknown"
    }
}

func participantSummary(_ participant: EKParticipant?) -> ParticipantSummary? {
    guard let participant else { return nil }
    return ParticipantSummary(
        name: truncate(participant.name, to: 200),
        isCurrentUser: participant.isCurrentUser,
        role: participantRole(participant.participantRole),
        status: participantStatus(participant.participantStatus)
    )
}

func currentUserAttendee(_ attendees: [EKParticipant]?) -> ParticipantSummary? {
    participantSummary(attendees?.first(where: { $0.isCurrentUser }))
}

func writeJSON<T: Encodable>(_ value: T) throws {
    let encoder = JSONEncoder()
    encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
    encoder.dateEncodingStrategy = .iso8601
    FileHandle.standardOutput.write(try encoder.encode(value))
    FileHandle.standardOutput.write(Data("\n".utf8))
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
let arguments = Array(CommandLine.arguments.dropFirst())
if arguments.count == 3 && arguments[0] == "--event-status" {
    let expectedOccurrence = arguments[2] == "-"
        ? nil
        : ISO8601DateFormatter().date(from: arguments[2])
    guard let event = store.event(withIdentifier: arguments[1]) else {
        try writeJSON(EventStatusResult(status: "cancelled", reason: "calendar event was removed"))
        exit(0)
    }
    if let expectedOccurrence {
        guard let actualOccurrence = event.occurrenceDate,
              abs(actualOccurrence.timeIntervalSince(expectedOccurrence)) <= 1 else {
            try writeJSON(EventStatusResult(
                status: "unknown",
                reason: "calendar occurrence identity could not be confirmed"
            ))
            exit(0)
        }
    }
    if event.status == .canceled {
        try writeJSON(EventStatusResult(status: "cancelled", reason: "calendar event is cancelled"))
        exit(0)
    }
    if event.attendees?.first(where: { $0.isCurrentUser })?.participantStatus == .declined {
        try writeJSON(EventStatusResult(status: "cancelled", reason: "Bryan declined the calendar event"))
        exit(0)
    }
    try writeJSON(EventStatusResult(status: "active", reason: "calendar event is still active"))
    exit(0)
}
let start = systemCalendar.startOfDay(for: Date())
let requestedDays = arguments.first.flatMap(Int.init) ?? 1
guard (1...31).contains(requestedDays) else {
    FileHandle.standardError.write(Data("Calendar lookahead must be between 1 and 31 days.\n".utf8))
    exit(2)
}
let end = systemCalendar.date(byAdding: .day, value: requestedDays, to: start)!
let predicate = store.predicateForEvents(withStart: start, end: end, calendars: nil)
let records = store.events(matching: predicate)
    .sorted { $0.startDate < $1.startDate }
    .map {
        CalendarEvent(
            eventIdentifier: $0.eventIdentifier,
            occurrenceDate: $0.occurrenceDate,
            source: "apple_calendar",
            calendar: $0.calendar.title,
            title: $0.title ?? "(untitled)",
            start: $0.startDate,
            end: $0.endDate,
            allDay: $0.isAllDay,
            location: truncate($0.location, to: 300),
            url: $0.url?.absoluteString,
            organizer: participantSummary($0.organizer),
            currentUserAttendee: currentUserAttendee($0.attendees),
            attendeeCount: $0.attendees?.count ?? 0
        )
    }

try writeJSON(records)
