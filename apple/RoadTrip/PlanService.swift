import Foundation

/// Talks to the roadTrip backend's `POST /plan` endpoint.
struct PlanService {
    var baseURL: URL
    var session: URLSession = .shared

    func plan(_ request: PlanRequest) async throws -> PlanResponse {
        let url = baseURL.appendingPathComponent("plan")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.timeoutInterval = 90  // the LLM planner can take a little while

        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        req.httpBody = try encoder.encode(request)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: req)
        } catch {
            throw PlanError.transport(error.localizedDescription)
        }

        guard let http = response as? HTTPURLResponse else {
            throw PlanError.transport("Unexpected response from server.")
        }
        guard (200..<300).contains(http.statusCode) else {
            throw PlanError.http(status: http.statusCode, body: Self.detail(from: data))
        }

        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        do {
            return try decoder.decode(PlanResponse.self, from: data)
        } catch {
            throw PlanError.decoding(error.localizedDescription)
        }
    }

    /// Pull FastAPI's `{"detail": ...}` out of an error body when present.
    private static func detail(from data: Data) -> String {
        if let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
            if let detail = obj["detail"] as? String { return detail }
            if let detail = obj["detail"] { return String(describing: detail) }
        }
        return String(data: data, encoding: .utf8) ?? ""
    }
}

enum PlanError: LocalizedError {
    case transport(String)
    case http(status: Int, body: String)
    case decoding(String)

    var errorDescription: String? {
        switch self {
        case .transport(let message):
            return "Couldn't reach the server. Check the backend URL in Settings and that it's running.\n\n\(message)"
        case .http(let status, let body):
            if status == 422 {
                return "The trip details were incomplete. Add a destination, attraction, direction, or idea."
            }
            return "Server returned \(status).\n\n\(body)"
        case .decoding(let message):
            return "Couldn't read the plan from the server.\n\n\(message)"
        }
    }
}
