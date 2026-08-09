# Image Processor - Design

## Objective

Build a service for uploading and serving optimized images for web applications handling resizing and format conversion automatically.

## Non-goals

Support for anything other than images. This is not a media processor.

## Architecture — Tech Stack

- CDK
- Github Actions
- Python 3.14
- AWS Lambda Powertools
- uv

## Architecture Diagram

## API Definition

`POST upload`

Response:

```json
{
    "image_id": "server side generated guid",
    "upload_url": "presigned url to upload source image"
}
```

`GET status/{guid}`

Response:

```json
{
    "status": "pending|processing|complete|failed",
    "images": {
        "thumb": "https://thumbnail-uri",
        "full": "https://full-uri"
    }
}
```

## User Flow

- Request a presigned url
- Poll a status endpoint
- On complete response will include urls for thumb and large image

## Worker Flow

- S3 put events written to an SQS queue
- Lambda event source for the queue
- Loads and resizes images

## Error Handling & Retry Strategy

- SQS DLQ
- Handle unsupported images by marking as failed in SQS - Does that put them back in the queue for another round?

## Persistence & State Transitions

- User requests an upload URL
- Record written to DDB recording the generated guid and pending status
- Processor lambda gets S3 put events via SQS, it sets processing
- When done, it sets complete
- Update logic needs to support going right from pending to complete even if that won't happen in this implementation
- TTL on records

## S3 Key Convention

`uploads/{guid}` - original image
`processed/{guid}/thumb.webp`
`processed/{guid}/display.webp`

## Image Resizing Strategy

- Fixed width for thumbs and display
- 80% original quality
- Large images?
- Smaller than min width images?


## Non-Functional Requirements

- Alarms on SQS queue and DDB table records to flag errors
