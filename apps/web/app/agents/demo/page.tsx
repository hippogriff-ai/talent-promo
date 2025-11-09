import AgentEventsStream from "../../components/AgentEventsStream";

export default function AgentDemo() {
  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto py-8">
        <div className="mb-8 text-center">
          <h1 className="text-4xl font-bold mb-2">Agent Events Stream Demo</h1>
          <p className="text-gray-600">Watch an AI agent work in real-time</p>
        </div>
        <AgentEventsStream agentId="demo-agent-123" />
      </div>
    </div>
  );
}
