import client from './client';


export async function listTenantUsers() {
  const res = await client.get('/api/v1/tenants/users');
  return res.data;
}


export async function inviteTenantUser(payload) {
  const res = await client.post('/api/v1/tenants/invite', payload);
  return res.data;
}


export async function updateTenantUserRole(userId, role) {
  const res = await client.put(`/api/v1/tenants/users/${userId}/role`, { role });
  return res.data;
}


export async function removeTenantUser(userId) {
  await client.delete(`/api/v1/tenants/users/${userId}`);
}
