import "@typespec/json-schema";
using TypeSpec.JsonSchema;

namespace DeclarativeMigrationsTest.PeerAuthority;

@id("EngineKind")
enum EngineKind {
  postgres: "postgres",
  cockroach: "cockroachdb",
}

@id("MigrationIntent")
@extension("additionalProperties", false)
model MigrationIntent {
  @minLength(1)
  migrationId: string;
  engine: EngineKind;
  @minLength(1)
  desiredStateDigest: string;
  transactional: boolean;
}
