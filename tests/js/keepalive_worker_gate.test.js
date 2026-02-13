const test = require('node:test');
const assert = require('node:assert/strict');

const { _test } = require('../../.github/scripts/keepalive_worker_gate.js');

function createGithubMock({ comments, reactionsByCommentId, headSha }) {
  const listComments = async () => ({ data: comments });
  const listForIssueComment = async () => ({ data: [] });

  const github = {
    rest: {
      pulls: {
        get: async () => ({
          data: {
            body: '<!-- meta:issue:50 -->',
            title: 'Automation PR for #50',
            head: {
              sha: headSha,
              ref: 'codex/issue-50',
              repo: { fork: false, owner: { login: 'acme' } },
            },
            base: {
              ref: 'main',
              repo: { owner: { login: 'acme' } },
            },
          },
        }),
      },
      issues: {
        listComments,
      },
      reactions: {
        listForIssueComment,
      },
    },
    paginate: async (method, params) => {
      if (method === listComments) {
        return comments;
      }
      if (method === listForIssueComment) {
        return reactionsByCommentId[params.comment_id] || [];
      }
      return [];
    },
  };

  return github;
}

function createInstructionComment({ id, createdAt }) {
  return {
    id,
    created_at: createdAt,
    html_url: `https://example.invalid/comment/${id}`,
    user: { login: 'stranske' },
    body: [
      '<!-- codex-keepalive-marker -->',
      '<!-- codex-keepalive-round: 2 -->',
      '<!-- codex-keepalive-trace: trace-abc -->',
      '@codex keepalive workflow continues nudging until everything is complete',
    ].join('\n'),
  };
}

function createStateComment({ id, lastInstructionId, lastHeadSha }) {
  return {
    id,
    created_at: '2026-02-13T02:00:00Z',
    user: { login: 'stranske-automation-bot' },
    body: `<!-- keepalive-state:v1 {"last_instruction":{"comment_id":"${lastInstructionId}","head_sha":"${lastHeadSha}"}} -->`,
  };
}

test('keepalive worker gate skips when latest lock-held instruction matches state', async () => {
  const instructionComment = createInstructionComment({ id: 200, createdAt: '2026-02-13T02:01:00Z' });
  const stateComment = createStateComment({ id: 210, lastInstructionId: 200, lastHeadSha: 'abc123' });
  const github = createGithubMock({
    comments: [instructionComment, stateComment],
    reactionsByCommentId: {
      200: [{ content: 'rocket' }, { content: 'hooray' }],
    },
    headSha: 'abc123',
  });

  const result = await _test.evaluateKeepaliveWorkerGate({
    core: { info() {}, warning() {} },
    github,
    context: { repo: { owner: 'acme', repo: 'counter-risk' } },
    env: { KEEPALIVE: 'true', PR_NUMBER: '77' },
  });

  assert.equal(result.action, 'skip');
  assert.equal(result.reason, 'no-new-instruction-and-head-unchanged');
  assert.equal(result.instructionId, '200');
  assert.equal(result.trace, 'trace-abc');
});

test('keepalive worker gate executes when lock-held instruction is newer than state', async () => {
  const instructionComment = createInstructionComment({ id: 305, createdAt: '2026-02-13T02:05:00Z' });
  const stateComment = createStateComment({ id: 310, lastInstructionId: 300, lastHeadSha: 'abc123' });
  const github = createGithubMock({
    comments: [instructionComment, stateComment],
    reactionsByCommentId: {
      305: [{ content: 'rocket' }, { content: 'hooray' }],
    },
    headSha: 'abc123',
  });

  const result = await _test.evaluateKeepaliveWorkerGate({
    core: { info() {}, warning() {} },
    github,
    context: { repo: { owner: 'acme', repo: 'counter-risk' } },
    env: { KEEPALIVE: 'true', PR_NUMBER: '77' },
  });

  assert.equal(result.action, 'execute');
  assert.equal(result.reason, 'new-instruction');
  assert.equal(result.instructionId, '305');
  assert.equal(result.trace, 'trace-abc');
});
