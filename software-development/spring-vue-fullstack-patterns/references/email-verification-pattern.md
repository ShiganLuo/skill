# Email Verification Code Registration Pattern

## Backend

### Dependencies
```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-mail</artifactId>
</dependency>
```

### Config (application-prod.yml)
```yaml
spring:
  mail:
    host: smtpdm.aliyun.com
    port: 465
    username: bio@mail.shiganluo.top
    password: <16-digit-auth-code>
    properties:
      mail:
        smtp:
          auth: true
          ssl:
            enable: true
          socketFactory:
            port: 465
            class: javax.net.ssl.SSLSocketFactory
            fallback: false
```

### EmailCodeService
- Generate 6-digit code: `(int)((Math.random() * 9 + 1) * 100000)`
- Store in Redis with 5-min TTL: `redisTemplate.opsForValue().set(key, code, 5, TimeUnit.MINUTES)`
- Send via `SimpleMailMessage` + `JavaMailSender`
- Verify: compare cached code, delete on success

### API Endpoints
- `POST /api/front/auth/sendEmailCode` — {email} → sends code (whitelist)
- `POST /api/front/auth/register` — {username, email, password, nickName, verifyCode} → validates code then registers

### FrontendRegisterRequest DTO
Add `verifyCode` field to the record.

## Frontend

### Register Form Fields
- Username, Nickname, Email, **Verify Code** (with send button), Password, Confirm Password

### Send Code Button
- 60-second cooldown after sending
- Disable button during cooldown, show countdown
- Validate email format before sending

### API
```typescript
export function sendEmailCode(email: string) {
  return http.post('/api/front/auth/sendEmailCode', { email })
}
```
