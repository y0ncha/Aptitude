# app.interface.dto module

Request and response DTOs for the public HTTP contract.

## Purpose

Defines Pydantic models and example payloads for publish, discovery,
resolution, exact immutable metadata fetch, and lifecycle-status APIs.

## Notes

- DTOs should mirror the public contract only; they should not preserve deleted
  route shapes.
- Raw markdown content fetch is modeled directly as an HTTP response, so this
  module keeps the immutable metadata envelope but not a markdown-body DTO.
