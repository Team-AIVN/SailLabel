"""SVG sanitization on workspace file uploads (parity with the old project import path)."""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from organizations.models import OrganizationMember
from organizations.tests.factories import OrganizationFactory
from rest_framework.test import APITestCase
from workspaces.models import Workspace, WorkspaceFileUpload, WorkspaceMember

MALICIOUS_SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)">'
    b'<script>alert("xss")</script>'
    b'<rect width="10" height="10"/>'
    b'</svg>'
)


class WorkspaceSvgUploadTests(APITestCase):
    def setUp(self):
        self.org = OrganizationFactory()
        self.owner = self.org.created_by
        self.owner.active_organization = self.org
        self.owner.save(update_fields=['active_organization'])
        OrganizationMember.objects.get_or_create(user=self.owner, organization=self.org)
        self.ws = Workspace.objects.create(organization=self.org, title='WS', created_by=self.owner)
        WorkspaceMember.objects.create(workspace=self.ws, user=self.owner, role=WorkspaceMember.Role.WORKSPACE_MANAGER)
        self.client.force_authenticate(user=self.owner)

    def _upload(self):
        svg = SimpleUploadedFile('x.svg', MALICIOUS_SVG, content_type='image/svg+xml')
        resp = self.client.post(f'/api/workspaces/{self.ws.id}/import/', {'x.svg': svg}, format='multipart')
        assert resp.status_code == 201, resp.content
        upload = WorkspaceFileUpload.objects.get(id=resp.json()['file_upload_ids'][0])
        upload.file.open('rb')
        try:
            return upload.file.read().decode('utf-8', 'replace')
        finally:
            upload.file.close()

    @override_settings(SVG_SECURITY_CLEANUP=True)
    def test_svg_sanitized_when_enabled(self):
        content = self._upload()
        assert '<script' not in content.lower()
        assert 'alert(' not in content
        # allowed shape tags survive the cleaner
        assert 'rect' in content.lower()

    @override_settings(SVG_SECURITY_CLEANUP=False)
    def test_svg_untouched_when_disabled(self):
        content = self._upload()
        # no cleanup configured -> stored verbatim (matches legacy project behavior)
        assert '<script' in content.lower()
