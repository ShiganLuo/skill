# Agent Shell Execution Tool Pattern

Giving an AI Agent shell execution capability in a Spring Boot application. Enables the LLM to access any server data (files, databases, bioinformatics tools) without writing dedicated Tool classes for each query.

## Architecture: Layered Command Routing

```
shell_execute command
       │
  ┌────┴────┐
  ▼         ▼
Local      Worker
(ProcessBuilder)  (HTTP forwarding)
```

- **Local execution**: lightweight read-only commands (`ls`, `find`, `df`, `mysql -e SELECT`, `cat`, `head`)
- **Worker forwarding**: bioinformatics compute tools (`samtools`, `bcftools`, `bwa`, `gatk`, `fastqc`)

Route by checking the first token against a known set of bio tools:

```java
private static final Set<String> BIO_TOOLS = Set.of(
    "samtools", "bcftools", "bwa", "bwa-mem2", "bowtie2", "hisat2", "STAR",
    "gatk", "freebayes", "fastqc", "multiqc", "trimmomatic", "fastp",
    "bedtools", "deeptools", "stringtie", "featurecounts",
    "blast", "blastn", "blastp", "hmmmer", "plink", "vcftools"
);

private boolean isBioCommand(String command) {
    String firstToken = command.trim().split("\\s+")[0];
    if (firstToken.contains("/")) firstToken = firstToken.substring(firstToken.lastIndexOf('/') + 1);
    return BIO_TOOLS.contains(firstToken);
}
```

## Security: Command Blacklist

Block dangerous operations at the tool level. Use regex patterns, not string matching:

```java
private static final List<Pattern> BLOCKED_PATTERNS = List.of(
    Pattern.compile("\\brm\\s+(-[a-zA-Z]*\\s+)*-?rf\\b"),
    Pattern.compile("\\bmkfs\\b"),
    Pattern.compile("\\bdd\\s+if="),
    Pattern.compile("\\bshutdown\\b"),
    Pattern.compile("\\breboot\\b"),
    // SQL write operations
    Pattern.compile("\\bDROP\\s+DATABASE\\b", Pattern.CASE_INSENSITIVE),
    Pattern.compile("\\bDELETE\\s+FROM\\b", Pattern.CASE_INSENSITIVE),
    Pattern.compile("\\bTRUNCATE\\b", Pattern.CASE_INSENSITIVE),
    Pattern.compile("\\bUPDATE\\b.*\\bSET\\b", Pattern.CASE_INSENSITIVE),
    Pattern.compile("\\bINSERT\\s+INTO\\b", Pattern.CASE_INSENSITIVE),
    // Fork bombs and remote pipe execution
    Pattern.compile("\\b:\\(\\)\\{"),
    Pattern.compile("\\bcurl\\b.*\\|\\s*bash"),
    Pattern.compile("\\bwget\\b.*\\|\\s*bash")
);
```

## Output Truncation

LLM context is limited. Truncate command output to prevent overflow:

```java
private static final int MAX_OUTPUT_CHARS = 10240;

private String readProcessOutput(Process process, int timeout) {
    StringBuilder sb = new StringBuilder();
    try (BufferedReader reader = new BufferedReader(
            new InputStreamReader(process.getInputStream(), StandardCharsets.UTF_8))) {
        String line;
        while ((line = reader.readLine()) != null) {
            sb.append(line).append("\n");
            if (sb.length() > MAX_OUTPUT_CHARS) {
                sb.append("\n... [输出已截断，超过 ").append(MAX_OUTPUT_CHARS).append(" 字符]");
                break;
            }
        }
    }
    return sb.toString();
}
```

## Process Execution with Timeout

```java
ProcessBuilder pb = new ProcessBuilder("bash", "-c", command);
pb.redirectErrorStream(true);
if (workdir != null) pb.directory(new File(workdir));

Process process = pb.start();
String output = readProcessOutput(process, timeout);

boolean finished = process.waitFor(timeout, TimeUnit.SECONDS);
int exitCode = finished ? process.exitValue() : -1;
if (!finished) process.destroyForcibly();
```

## Worker Forwarding

Reuse existing WorkerClient infrastructure. Submit task → poll for result:

```java
private String executeOnWorker(String command, int timeout, String workdir) {
    List<WorkerInfo> workers = workerRegistry.getHealthyWorkers();
    if (workers.isEmpty()) return toJson(-1, "没有可用的计算节点");

    WorkerInfo worker = workers.get(0);
    Map<String, Object> body = Map.of("command", command, "timeout", timeout);
    String response = HttpUtil.post(worker.getUrl() + "/worker/tasks/submit", objectMapper.writeValueAsString(body));
    String taskId = objectMapper.readTree(response).get("taskId").asText();

    // Poll for completion
    long deadline = System.currentTimeMillis() + timeout * 1000L;
    while (System.currentTimeMillis() < deadline) {
        String status = workerClient.queryTaskStatus(worker.getUrl(), taskId);
        if ("COMPLETED".equals(status) || "FAILED".equals(status)) {
            return workerClient.getTaskOutput(worker.getUrl(), taskId);
        }
        Thread.sleep(1000);
    }
    return "等待 Worker 结果超时";
}
```

## Tool Auto-Registration

Spring auto-discovers all `@Component` classes implementing `Tool`. Just annotate:

```java
@Component
public class ShellExecuteTool implements Tool { ... }
```

No manual registration needed in `AgentToolExecutor`.

## Agent Tool Assignment Strategy

Keep specialized tools for high-frequency structured queries (they return cleaner data). Add `shell_execute` as a universal fallback to all agents:

```java
// QAAgent — all tools (default router, general-purpose)
public List<ToolDefinition> getTools() { return toolExecutor.getAllToolDefinitions(); }

// PipelineAgent — specialized + shell
.filter(t -> "pipeline_list".equals(t.name()) || "shell_execute".equals(t.name()) || ...)

// DataAnalysisAgent — specialized + shell
.filter(t -> "file_info".equals(t.name()) || "format_info".equals(t.name()) || "shell_execute".equals(t.name()))
```

## System Prompt: Shell Usage Guide

Include shell command examples in the agent's system prompt so the LLM knows what's available:

```
常用命令参考：
- 查看项目: mysql -u root bioplatform -e "SELECT id,name,organism FROM projects"
- 查看文件: mysql -u root bioplatform -e "SELECT id,name,file_type FROM data_files"
- 浏览文件系统: ls -la /data/
- 检查磁盘: df -h
- 生信工具: samtools flagstat /path/to/file.bam
```

## Config Toggle

```yaml
# application-docker.yml
agent:
  shell:
    enabled: ${AGENT_SHELL_ENABLED:true}
```

## Pitfalls

- **Don't create dedicated Tool classes for every query** — the user's intent is "let the agent figure it out with shell". Write one `ShellExecuteTool` and let the LLM compose commands.
- **SQL blacklist must cover DDL+DML** — the tool blocks INSERT/UPDATE/DELETE/DROP/TRUNCATE/ALTER/CREATE. Only SELECT is allowed through mysql CLI.
- **First-token routing must strip paths** — `/usr/bin/samtools flagstat` should still route to Worker. Extract just the basename before checking BIO_TOOLS.
- **Worker polling must have timeout** — don't loop forever. Use the command's timeout value as the polling deadline.
