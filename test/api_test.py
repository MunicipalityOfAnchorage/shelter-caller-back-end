from datetime import date, timedelta
import pytest
from unittest.mock import Mock, patch
from flask import g
from flask_jwt_simple import create_jwt
from app.models import Shelter
from app import db
from app.models import Count
from app.api.decorators import add_user, role_required
from app.exceptions import UnauthorizedUse


@patch('flask_jwt_simple.get_jwt_identity')
def test_role_required_decorator(jwtMock, app_with_envion_DB):
    '''@role_required() should call decorated function if user is in roles'''
    jwtMock.return_value = 'admin'
    f = Mock()
    role_required(['minion', 'admin'])(f)()
    f.assert_called()
    assert any(r.name == 'admin' for r in g.user.roles)


@patch('flask_jwt_simple.get_jwt_identity')
def test_role_required_unauthorized_decorator(jwtMock, app_with_envion_DB):
    '''@role_required() should raise Unauthorized if user is not in roles'''
    jwtMock.return_value = 'visitor'
    f = Mock()
    with pytest.raises(UnauthorizedUse):
        role_required(['minion', 'admin'])(f)()


@patch('flask_jwt_simple.get_jwt_identity')
def test_role_required_unknown_decorator(jwtMock, app_with_envion_DB):
    '''@role_required() should raise Unauthorized if user is not known'''
    jwtMock.return_value = 'hacker'
    f = Mock()
    with pytest.raises(UnauthorizedUse):
        role_required(['minion', 'admin'])(f)()


@patch('flask_jwt_simple.get_jwt_identity')
def test_add_user_decorator(jwtMock, app_with_envion_DB):
    '''@add_user() should includes users roles from DB to g.'''
    jwtMock.return_value = 'admin'
    f = Mock()
    add_user()(f)()
    f.assert_called()
    assert any(r.name == 'admin' for r in g.user.roles)


@patch('flask_jwt_simple.get_jwt_identity')
def test_add_user_decorator_adds_user(jwtMock, app_with_envion_DB):
    '''@add_user() should add user from DB to g.'''
    jwtMock.return_value = 'admin'
    f = Mock()
    add_user()(f)()
    f.assert_called()
    assert g.user.username == 'admin'


def test_add_user_decorator_no_user(app_with_envion_DB):
    '''@add_user() should work with noo JWT user.'''
    f = Mock()
    add_user()(f)()
    f.assert_called()
    assert 'user' not in g


def test_get_shelters_auth(app_with_envion_DB):
    jwt = create_jwt(identity="admin")

    client = app_with_envion_DB.test_client()
    rv = client.get('/api/shelters/', environ_base={'HTTP_AUTHORIZATION': 'Bearer ' + jwt})
    assert rv.status_code == 200


def test_get_shelters_no_auth(app_with_envion_DB, test_shelters):
    '''/api/shelters should return 401 when auth is not present '''

    for s in test_shelters:
        db.session.add(Shelter(**s))

    db.session.commit()

    client = app_with_envion_DB.test_client()

    rv = client.get('/api/shelters/')
    assert rv.status_code == 401


def test_admin_login_good(app_with_envion_DB):
    '''should return a token and roles to authorized user'''
    client = app_with_envion_DB.test_client()
    rv = client.post(
        '/api/admin_login/',
        json={"user": "admin", "password": "password"}
    )
    json_response = rv.get_json()
    assert rv.status_code == 200
    assert 'jwt' in json_response
    assert json_response['roles'] == ['admin']


def test_admin_no_user(app_with_envion_DB):
    '''should return 400 when login is incomplete'''
    client = app_with_envion_DB.test_client()
    rv = client.post(
        '/api/admin_login/',
        json={"password": "password"}
    )
    assert rv.status_code == 400
    assert 'jwt' not in rv.get_json()


def test_admin_unauthorized(app_with_envion_DB):
    '''should return 401 for unknown logins'''
    client = app_with_envion_DB.test_client()
    rv = client.post(
        '/api/admin_login/',
        json={"user": "admin", "password": "bad_password"}
    )
    assert rv.status_code == 401
    assert 'jwt' not in rv.get_json()


def test_counts_today(app_with_envion_DB, counts):
    '''should provide counts for all shelters (even if they have no count)'''
    client = app_with_envion_DB.test_client()
    rv = client.get('/api/counts/')
    responses = rv.get_json()['counts']

    assert len(responses) == 2
    assert any(count['bedcount'] == 100 and count['id'] == 1 for count in responses)
    assert any(count['bedcount'] is None and count['id'] == 2 for count in responses)


def test_counts_previous(app_with_envion_DB, counts):
    '''should provide counts for all shelters (even if they have no count)'''
    client = app_with_envion_DB.test_client()
    rv = client.get('/api/counts/')
    responses = rv.get_json()['counts']

    assert len(responses) == 2
    assert any(count['bedcount'] == 100 and count['id'] == 1 for count in responses)
    assert any(count['bedcount'] is None and count['id'] == 2 for count in responses)


def test_counts_future_tomorrow(app_with_envion_DB, counts):
    '''should only provide a link to yesterday when getting today's counts'''
    client = app_with_envion_DB.test_client()
    rv = client.get('/api/counts/')
    responses = rv.get_json()
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y%m%d')
    assert responses['tomorrow'] is None
    assert responses['yesterday'] == yesterday


def test_counts_yesterday(app_with_envion_DB, counts):
    '''should report counts for shelters from previous days'''
    client = app_with_envion_DB.test_client()
    yesterday = yesterday = (date.today() - timedelta(days=1)).strftime('%Y%m%d')
    rv = client.get(f'/api/counts/{yesterday}')
    responses = rv.get_json()['counts']

    assert len(responses) == 2
    assert any(count['bedcount'] == 31 and count['id'] == 1 for count in responses)
    assert any(count['bedcount'] == 32 and count['id'] == 2 for count in responses)


def test_counts_next_previous(app_with_envion_DB, counts):
    '''should provide links to yesterday and tomorrow for past count queries'''
    client = app_with_envion_DB.test_client()
    yesterday = yesterday = (date.today() - timedelta(days=1)).strftime('%Y%m%d')
    rv = client.get(f'/api/counts/{yesterday}')
    responses = rv.get_json()
    today = date.today().strftime('%Y%m%d')
    daybefore = (date.today() - timedelta(days=2)).strftime('%Y%m%d')
    assert responses['tomorrow'] == today
    assert responses['yesterday'] == daybefore


def test_set_count(app_with_envion_DB, counts):
    '''should update count for given shelter and day'''
    client = app_with_envion_DB.test_client()
    yesterday = (date.today() - timedelta(days=1))
    jwt = create_jwt(identity='admin')
    rv = client.post(
        '/api/setcount/',
        json={"numberOfPeople": 66, "shelterID": 1, "day": yesterday},
        headers={"Authorization": "Bearer " + jwt}
    )

    count = Count.query.filter_by(day=yesterday, shelter_id=1).first()
    assert rv.status_code == 200
    assert count.personcount == 66


def test_delete_count(app_with_envion_DB, counts):
    '''should delete count for given shelter and day if count is not given'''
    client = app_with_envion_DB.test_client()
    yesterday = (date.today() - timedelta(days=1))
    jwt = create_jwt(identity='admin')
    rv = client.post(
        '/api/setcount/',
        json={"shelterID": 1, "day": yesterday},
        headers={"Authorization": "Bearer " + jwt}
    )

    count = Count.query.filter_by(day=yesterday, shelter_id=1).first()
    assert rv.status_code == 200
    assert count is None


def test_counthistory(app_with_envion_DB, counts):
    '''Count history should return 14 dates and one series per visible, public shelter'''
    client = app_with_envion_DB.test_client()
    rv = client.get('/api/counthistory/')
    assert rv.status_code == 200
    data = rv.get_json()
    assert len(data['dates']) == 14
    assert len(data['shelters']) > 0
    for shelter in data['shelters']:
        assert len(shelter['data']) == 14


def test_export(app_with_envion_DB, counts):
    '''CSV export should return every count'''
    client = app_with_envion_DB.test_client()
    rv = client.get('/api/k1/export/')
    assert rv.status_code == 200
    lines = rv.get_data(as_text=True).strip().splitlines()
    assert len(lines) == 4  # header + three counts
    rv = client.get('/api/k2/export/')
    assert rv.status_code == 200


def test_admin_login_upgrades_plaintext_password(app_with_envion_DB):
    '''A plain-text password should be replaced with a hash on the first good login'''
    from app.models import User
    client = app_with_envion_DB.test_client()
    assert User.query.filter_by(username='admin').first().password == 'password'

    rv = client.post('/api/admin_login/', json={"user": "admin", "password": "password"})
    assert rv.status_code == 200
    stored = User.query.filter_by(username='admin').first().password
    assert stored != 'password'
    assert stored.startswith(('pbkdf2:', 'scrypt:'))

    # the hashed password still works, and a wrong one is still refused
    rv = client.post('/api/admin_login/', json={"user": "admin", "password": "password"})
    assert rv.status_code == 200
    rv = client.post('/api/admin_login/', json={"user": "admin", "password": "bad_password"})
    assert rv.status_code == 401


def test_admin_login_hash_is_not_a_password(app_with_envion_DB):
    '''Someone who obtains the stored hash must not be able to log in with it'''
    from app.models import User
    client = app_with_envion_DB.test_client()
    client.post('/api/admin_login/', json={"user": "admin", "password": "password"})
    stored = User.query.filter_by(username='admin').first().password
    rv = client.post('/api/admin_login/', json={"user": "admin", "password": stored})
    assert rv.status_code == 401


def test_counthistory_values_line_up_with_dates(app_with_envion_DB, counts):
    '''Each shelter's data should be in the same order as the dates'''
    from datetime import date, timedelta
    client = app_with_envion_DB.test_client()
    data = client.get('/api/counthistory/').get_json()
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    by_day = {s['label']: dict(zip(data['dates'], s['data'])) for s in data['shelters']}
    values = sorted(str(v.get(today)) + '/' + str(v.get(yesterday)) for v in by_day.values())
    assert values == ['20/20', 'None/10']


def test_set_count_shelter_without_capacity(app_with_envion_DB, test_shelters):
    '''An admin should be able to set a count for a shelter saved without a capacity'''
    db.session.add(Shelter(**dict(test_shelters[0], capacity=None)))
    db.session.commit()
    client = app_with_envion_DB.test_client()
    jwt = create_jwt(identity='admin')
    rv = client.post(
        '/api/setcount/',
        json={"numberOfPeople": 7, "shelterID": 1, "day": date.today()},
        headers={"Authorization": "Bearer " + jwt}
    )
    assert rv.status_code == 200
    count = Count.query.filter_by(shelter_id=1).one()
    assert count.personcount == 7
    assert count.bedcount == 0


def test_set_count_unknown_shelter(app_with_envion_DB):
    '''Setting a count for a shelter that doesn't exist should be refused, not crash'''
    client = app_with_envion_DB.test_client()
    jwt = create_jwt(identity='admin')
    rv = client.post(
        '/api/setcount/',
        json={"numberOfPeople": 7, "shelterID": 4242, "day": date.today()},
        headers={"Authorization": "Bearer " + jwt}
    )
    assert rv.status_code == 404
    assert Count.query.count() == 0


def test_update_shelter_without_phone(app_with_envion_DB):
    '''The admin form sends an empty phone as the text "null"; two such shelters must both save with no phone'''
    client = app_with_envion_DB.test_client()
    jwt = create_jwt(identity='admin')
    for n, phone in enumerate(('null', 'undefined', ''), start=1):
        rv = client.post(
            '/api/update_shelter/',
            data={"name": f"no phone {n}", "login_id": 7000 + n, "capacity": 20, "phone": phone,
                  "description": "null", "active": "true", "visible": "true", "public": "true"},
            headers={"Authorization": "Bearer " + jwt}
        )
        assert rv.status_code == 200
    shelters = Shelter.query.all()
    assert len(shelters) == 3
    assert all(s.phone is None and s.description is None for s in shelters)
