# MyBatis Optional Filter/Search Pattern

When adding search/filter to a paginated list endpoint (with PageHelper), follow this 4-layer pattern.

## Mapper XML — optional `<if>` filters

```xml
<select id="selectByOwnerId" resultMap="BaseResultMap">
    SELECT <include refid="Base_Column_List"/>
    FROM `projects`
    WHERE `owner_id` = #{ownerId}
    <if test="status != null">
        AND `status` = #{status}
    </if>
    <if test="name != null and name != ''">
        AND (`name` LIKE CONCAT('%', #{name}, '%') OR `description` LIKE CONCAT('%', #{name}, '%'))
    </if>
    <if test="organism != null and organism != ''">
        AND `organism` LIKE CONCAT('%', #{organism}, '%')
    </if>
    ORDER BY `updated_at` DESC
</select>
```

Key points:
- Use `updated_at DESC` for "most recently modified first" (not `created_at`)
- Search multiple columns with `OR` in a single `<if>` block (name + description)
- All filter params are optional — omitting them returns unfiltered results
- `LIKE CONCAT('%', #{name}, '%')` for partial match

## Mapper Java interface

```java
List<Project> selectByOwnerId(@Param("ownerId") Long ownerId, @Param("status") Integer status,
                              @Param("name") String name, @Param("organism") String organism);
```

## Service — pass parameters through

```java
// Interface
PageResult listUserProjects(Long userId, int pageNum, int pageSize, String name, String organism);

// Impl
public PageResult listUserProjects(Long userId, int pageNum, int pageSize, String name, String organism) {
    PageHelper.startPage(pageNum, pageSize);
    List<Project> projects = projectMapper.selectByOwnerId(userId, null, name, organism);
    PageInfo<Project> pageInfo = new PageInfo<>(projects);
    return PageResult.of(pageInfo.getTotal(), pageNum, pageSize, projects);
}
```

## Controller — `@RequestParam(required = false)`

```java
@GetMapping("/list")
public ApiResponse<PageResult<Project>> list(
        @RequestParam(defaultValue = "1") int page,
        @RequestParam(defaultValue = "10") int size,
        @RequestParam(required = false) String name,
        @RequestParam(required = false) String organism) {
    Long userId = LoginUserHolder.getCurrentUserId();
    PageResult<Project> result = projectService.listUserProjects(userId, page, size, name, organism);
    return ApiResponse.success(result);
}
```

## Frontend — spread searchForm into params

```ts
const res = await listProjects({
    page: pagination.page,
    size: pagination.size,
    ...searchForm  // name, organism, etc.
})
```

## Why this works

- `@RequestParam(required = false)` allows the param to be absent from the request
- When frontend sends empty strings for unfilled fields, Spring receives empty strings
- MyBatis `<if test="name != null and name != ''">` handles both null and empty correctly
- PageHelper applies pagination AFTER the full query with filters
