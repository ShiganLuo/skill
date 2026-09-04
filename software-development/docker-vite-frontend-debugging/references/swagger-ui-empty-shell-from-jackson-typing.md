# Swagger UI empty shell from global Jackson default typing

Symptoms observed in this session:
- `/doc.html` and `/swagger-ui/index.html` loaded only a shell or an "Unable to render this definition" page.
- `/v3/api-docs` returned valid OpenAPI JSON with real paths.
- `/v3/api-docs/swagger-config` returned framework metadata such as `@class` and Java collection wrapper structures instead of plain JSON arrays/objects.
- Swagger UI showed either no content or invalid-definition errors because the config document was polluted.

Root cause:
- A Redis-specific `ObjectMapper` was declared as a global `@Bean` in `RedisConfig`.
- That mapper had `activateDefaultTyping(...)` enabled for Redis serialization.
- SpringDoc reused the same mapper for swagger-config serialization, which injected type metadata into config responses.

Fix pattern:
1. Keep the Redis mapper private/local instead of exposing it as a Spring bean.
2. Use that private mapper only inside `new GenericJackson2JsonRedisSerializer(redisObjectMapper())`.
3. Rebuild and recreate the backend container.
4. Verify `/v3/api-docs/swagger-config` is plain JSON without `@class` fields.
5. Verify Swagger UI can read `/v3/api-docs` normally.

Useful probes:
- `curl -s http://localhost:8080/v3/api-docs | head`
- `curl -s http://localhost:8080/v3/api-docs/swagger-config`
- Browser symptom: Swagger UI shell loads, but definitions fail to render despite valid `/v3/api-docs`.

Session note:
- Changing only `springdoc.swagger-ui.*` properties did not fix the root issue while `swagger-config` remained type-decorated.
- The durable fix was scoping the Redis ObjectMapper so SpringDoc no longer serialized config with Jackson default typing.
