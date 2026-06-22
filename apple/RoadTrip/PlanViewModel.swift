import Combine
import Foundation

@MainActor
final class PlanViewModel: ObservableObject {
    @Published var request = PlanRequest()
    @Published var result: PlanResponse?
    @Published var errorMessage: String?
    @Published var isLoading = false

    func plan(baseURL: URL) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            result = try await PlanService(baseURL: baseURL).plan(request)
        } catch {
            result = nil
            errorMessage = (error as? LocalizedError)?.errorDescription ?? error.localizedDescription
        }
    }
}
