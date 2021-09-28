import copy
import os
from datetime import datetime, timedelta
import itertools
import math
import logging
from concurrent.futures import ThreadPoolExecutor
from Database_Operator.Mongo_Operator import Mongo_Operate
from Math import Geometry
import numpy as np
import random


class RMDP:

    def __init__(self):
        self.DEBUG = False if int(os.environ['DEBUG']) == 1 else True
        # self.DEBUG = True
        self.S = 0
        self.time_buffer = timedelta(minutes=0)
        self.t_Pmax = timedelta(seconds=40)
        self.t_ba = 10
        self.delay = 5
        self.capacity = 5
        self.velocity: float = 50 * 0.2777777777777778
        self.restaurantPrepareTime = timedelta(minutes=20)
        self.deadlineTime = timedelta(minutes=40)

        self.DBclient = Mongo_Operate()

        self.p = math.pi / 180

    def generateThread(self):
        cityList = self.DBclient.getAllCity()  # get all city
        totalCurrentWorker = 2
        logging.info("start generating")
        with ThreadPoolExecutor(max_workers=totalCurrentWorker) as executor:
            threads = []
            for i in range(len(cityList)):
                threads.append(executor.submit(self.runRMDP, index=i, cityName=(cityList[i])))

    def runRMDP(self, index, cityName):
        try:
            delay = float("inf")
            slack = 0
            skipPostponement = False
            pairdOrder = []
            maxLengthPost = 5

            restaurantList = self.DBclient.getRestaurantListBaseOnCity(cityName['City'])

            filterrestTaurantCode = list(
                map(lambda x: int(x['Restaurant_ID']), restaurantList))  # set all restaurant_id to int

            finishedOrder = self.DBclient.getOrderBaseOnCity(filterrestTaurantCode, "delivered")
            finishOrder = list(order for order in finishedOrder if order['Qtable_updated'] == 0)
            q_setting = self.DBclient.getQlearning(cityName['City'])

            for forder in finishOrder:
                getrestaurant = next(
                    restaurant for restaurant in restaurantList if
                    int(restaurant['Restaurant_ID']) == int(forder["order_restaurant_carrier_restaurantId"]))

                time = datetime.strptime(forder['order_restaurant_carrier_date'],
                                         "%Y-%m-%d %H:%M:%S") - datetime.strptime(forder['order_request_time'],
                                                                                  "%d-%m-%Y %H:%M:%S")

                distance = Geometry.coorDistance(getrestaurant['Latitude'], getrestaurant['Longitude'],
                                                 forder['Latitude'], forder['Longitude'])  # meter
                reward = distance / (time.total_seconds() / 60)  # meter/second
                self.real_reward(forder, reward, q_setting)

            driverList = self.DBclient.getDriverBaseOnCity(cityName['City'])
            unAssignOrder = self.DBclient.getOrderBaseOnCity(filterrestTaurantCode,
                                                             "unassigned")  # get unassigned order
            postponedOrder = self.DBclient.getOrderBaseOnCity(filterrestTaurantCode, "waiting")  # get postpone order

            S = 0
            if len(unAssignOrder) == 0 and len(postponedOrder) > 0:
                skipPostponement = True
                unAssignOrder = copy.deepcopy(postponedOrder)
                postponedOrder.clear()
            if maxLengthPost <= len(unAssignOrder):
                maxLengthPost = len(unAssignOrder) + 1

            newDriverList = []
            newPospondedOrderList = []
            newPairedOrderList = []

            for permutation in itertools.permutations(unAssignOrder):

                currentDriverList = copy.deepcopy(driverList)
                P_hat = copy.deepcopy(postponedOrder)  # waitting order
                currentPairdOrder = copy.deepcopy(pairdOrder)

                for D in permutation:
                    currentPairdRestaurent = next(restaurant for restaurant in restaurantList if
                                                  restaurant['Restaurant_ID'] == D[
                                                      "order_restaurant_carrier_restaurantId"])
                    '''
                    currentPairdDriverId = self.Qing(D, currentPairdRestaurent, currentDriverList, cityName)
                    D["driver_id"] = currentDriverList[currentPairdDriverId]['Driver_ID']
                    currentDriverList[currentPairdDriverId]['Capacity'] += 1  # why assign twice
                    currentDriverList[currentPairdDriverId]['Route'] = copy.deepcopy(
                        self.AssignOrder(D, currentDriverList[currentPairdDriverId], currentPairdRestaurent))
                    '''

                    if skipPostponement:
                        currentPairdDriverId = self.Qing(D, currentPairdRestaurent, currentDriverList, cityName,
                                                         q_setting)
                        D["driver_id"] = currentDriverList[currentPairdDriverId]['Driver_ID']
                        currentDriverList[currentPairdDriverId]['Capacity'] += 1  # why assign twice
                        currentDriverList[currentPairdDriverId]['Route'] = copy.deepcopy(
                            self.AssignOrder(D, currentDriverList[currentPairdDriverId], currentPairdRestaurent))
                        currentPairdOrder.append(D)
                    else:
                        if self.Postponement(P_hat, D, maxLengthPost):
                            P_hat.append(D)
                        else:
                            while (datetime.strptime(D['order_request_time'], "%d-%m-%Y %H:%M:%S") - datetime.strptime(
                                    P_hat[0]['order_request_time'], "%d-%m-%Y %H:%M:%S")) >= self.t_Pmax:
                                PairedRestaurent = copy.deepcopy(next(restaurant for restaurant in restaurantList if
                                                                      restaurant['Restaurant_ID'] == P_hat[0][
                                                                          "order_restaurant_carrier_restaurantId"]
                                                                      ))
                                PairdDriverId = self.Qing(D, currentPairdRestaurent, currentDriverList, cityName,
                                                          q_setting)
                                P_hat[0]['driver_id'] = str(currentDriverList[PairdDriverId]['Driver_ID'])
                                currentDriverList[PairdDriverId]['Capacity'] += 1
                                currentDriverList[PairdDriverId]['Route'] = copy.deepcopy(
                                    self.AssignOrder(P_hat[0], currentDriverList[PairdDriverId], PairedRestaurent))
                                pairdOrder.append(P_hat[0])  # add finish order
                                P_hat.pop(0)
                                if len(P_hat) == 0:
                                    break
                            if len(P_hat) >= maxLengthPost:
                                # print("in")
                                for order in P_hat:
                                    PairedRestaurent = copy.deepcopy(next(
                                        restaurant for restaurant in restaurantList if
                                        int(restaurant['Restaurant_ID']) == int(
                                            order["order_restaurant_carrier_restaurantId"])))
                                    PairdDriverId = self.Qing(D, currentPairdRestaurent, currentDriverList, cityName,
                                                              q_setting)
                                    currentDriverList[PairdDriverId]['Capacity'] += 1
                                    order['driver_id'] = str(currentDriverList[PairdDriverId]['Driver_ID'])
                                    currentDriverList[PairdDriverId]['Route'] = copy.deepcopy(
                                        self.AssignOrder(order, currentDriverList[PairdDriverId],
                                                         PairedRestaurent))
                                    pairdOrder.append(order)
                                P_hat.clear()
                            P_hat.append(D)

                S = self.TotalDelay(currentDriverList)
                currentSlack = self.Slack(currentDriverList)
                if (S < delay) or ((S == delay) and (currentSlack < slack)):
                    slack = currentSlack
                    delay = S
                    newDriverList = copy.deepcopy(currentDriverList)
                    newPospondedOrderList = copy.deepcopy(P_hat)
                    newPairedOrderList = copy.deepcopy(currentPairdOrder)

            driverList = copy.deepcopy(newDriverList)
            postponedOrder = copy.deepcopy(newPospondedOrderList)
            pairdOrder = copy.deepcopy(newPairedOrderList)

            for order in postponedOrder:
                '''
                currentPairedDriver = next(
                    driver for driver in driverList if str(driver['Driver_ID']) == str(order['driver_id']))
                '''
                index = 0
                for driver in range(0, len(driverList)):
                    if driverList[driver]['Driver_ID'] == order['driver_id']:
                        index = driver
                        break
                '''
                currentPairedDriverId = driverList.index(
                    currentPairedDriver) if currentPairedDriver in driverList else -1
                '''
                '''
                driverList[currentPairedDriverId]['Route'] = copy.deepcopy(list(filter(
                    lambda x: (int(x['nodeType']) == 0 and x['Order_ID'] != order['Order_ID']) or (  # why no string
                            int(x['nodeType']) == 1 and str(x['Order_ID']) != str(order['Order_ID'])),
                    driverList[currentPairedDriverId]['Route'])))
                driverList[currentPairedDriverId]['Capacity'] -= 1
                '''
                driverList[index]['Route'] = copy.deepcopy(list(filter(
                    lambda x: (int(x['nodeType']) == 0 and x['Order_ID'] != order['Order_ID']) or (  # why no string
                            int(x['nodeType']) == 1 and str(x['Order_ID']) != str(order['Order_ID'])),
                    driverList[index]['Route'])))
                driverList[index]['Capacity'] -= 1
            self.updateDriver(driverList)
            self.updatePosponedOrder(postponedOrder)
            self.updatePairdOrder(pairdOrder)
            print("Thread:", index, " is finished")
        except Exception as e:
            logging.critical(e, exc_info=True)

    def deltaSDelay(self, route, Longitude, Latitude):
        try:
            delay: float = 0.0
            tripTime: float = 0.0
            currentRoute = copy.deepcopy(route)
            currentRoute.insert(0, {"Longitude": Longitude, "Latitude": Latitude, 'nodeType': 2})
            for i in range(1, len(currentRoute), 1):
                previousNode = currentRoute[i - 1]
                currentNode = currentRoute[i]
                currentDistance = Geometry.coorDistance(float(previousNode['Latitude']),
                                                        float(previousNode['Longitude']),
                                                        float(currentNode['Latitude']), float(currentNode['Longitude']))
                tripTime += currentDistance / self.velocity
                if 'order_request_time' in currentNode:
                    timeComplete = timedelta(seconds=tripTime) + self.time_buffer + datetime.now() + timedelta(hours=8)
                    # print(timeComplete)
                    # print(currentNode['order_request_time'])
                    timeDeadline = datetime.strptime(currentNode['order_request_time'],
                                                     "%d-%m-%Y %H:%M:%S") + self.deadlineTime
                    # print(timeDeadline)
                    timeDelay = timeComplete - timeDeadline
                    delay += timeDelay.total_seconds()
            return max(0, delay)
        except Exception as e:
            logging.critical(e, exc_info=True)

    def AssignOrder(self, order, pairedDriver, currentParedRestaurent):
        try:
            if not pairedDriver['Route']:
                pairedDriver['Route'].append(currentParedRestaurent)
                pairedDriver['Route'].append(order)

                pairedDriver['Route'][0]['nodeType'] = 0
                pairedDriver['Route'][0]['Order_ID'] = order['Order_ID']

                pairedDriver['Route'][1]['nodeType'] = 1

            else:
                first: int = 0
                second: int = 1
                minDelayTime = float('inf')
                for i in range(0, len(pairedDriver['Route']), 1):
                    for j in range(i + 1, len(pairedDriver['Route']) + 2, 1):

                        tmpDriver = copy.deepcopy(pairedDriver)
                        tmpDriver['Route'].insert(i, currentParedRestaurent)
                        tmpDriver['Route'].insert(j, order)
                        delayTime = self.deltaSDelay(tmpDriver['Route'], tmpDriver['Latitude'], tmpDriver['Longitude'])

                        if minDelayTime > delayTime:
                            minDelayTime = delayTime
                            first = i
                            second = j

                pairedDriver['Route'].insert(first, currentParedRestaurent)
                pairedDriver['Route'][first]['nodeType'] = 0
                pairedDriver['Route'][first]['Order_ID'] = order['Order_ID']

                pairedDriver['Route'].insert(second, order)
                pairedDriver['Route'][second]['nodeType'] = 1
            return pairedDriver['Route']
        except Exception as e:
            logging.critical(e, exc_info=True)

    # main function

    def Slack(self, driverList):
        return sum(self.slackDelay(driver['Route'], driver['Latitude'], driver['Longitude']) for driver in driverList)

    def tripTime(self, driv, res, order):
        try:
            disDriver2Res = Geometry.coorDistance(float(driv['Latitude']), float(driv['Longitude']),
                                                  # get distance d->r
                                                  float(res['Latitude']),
                                                  float(res['Longitude']))
            Res2Delivery = Geometry.coorDistance(float(res['Latitude']), float(res['Longitude']),  # get distance r->o
                                                 float(order['Latitude']),
                                                 float(order['Longitude']))
            return float(disDriver2Res + Res2Delivery / float(self.velocity))  # time
        except Exception as e:
            logging.critical(e, exc_info=True)

    def FindVehicle(self, Order, OrderRestaurant, driverList):
        try:
            handleDriver = list(filter(lambda driver: int(driver['Capacity']) < int(self.capacity),
                                       driverList))  # get less than capacity driver
            distanceList = list(
                map(lambda x: self.tripTime(x, OrderRestaurant, Order), handleDriver))  # getall triptime
            return distanceList.index(min(distanceList))  # return min driver in index
        except Exception as e:
            logging.critical(e, exc_info=True)

    def slackDelay(self, route, Longitude, Latitude):
        try:
            delay: int = 0
            tripTime: int = 0
            currentRoute: list = copy.deepcopy(route)
            currentRoute.insert(0, {"Longitude": Longitude, "Latitude": Latitude, 'nodeType': 2})
            for i in range(1, len(currentRoute), 1):
                currentDistance = Geometry.coorDistance(float(currentRoute[i - 1]['Latitude']),
                                                        float(currentRoute[i - 1]['Longitude']),
                                                        float(currentRoute[i]['Latitude']),
                                                        float(currentRoute[i]['Longitude']))
                tripTime += currentDistance / self.velocity
                if 'restaurantId' in currentRoute[i]:
                    deadLine = currentRoute[i]['deadLineTime'] - datetime.now() + timedelta(hours=8)
                    delayTime = timedelta(seconds=tripTime) - timedelta(seconds=self.time_buffer) - deadLine
                    delay += max(0.0, delayTime.total_seconds())
            return delay
        except Exception as e:
            logging.critical(e, exc_info=True)

    def TotalDelay(self, driverList):
        try:
            return sum(
                self.deltaSDelay(driver['Route'], driver['Longitude'], driver['Latitude']) for driver in driverList)
        except Exception as e:
            logging.critical(e, exc_info=True)

    def Postponement(self, P_hat, D, maxLengthPost):
        try:
            if len(P_hat) < maxLengthPost or datetime.strptime(D['order_request_time'],
                                                               "%d-%m-%Y %H:%M:%S") - datetime.strptime(
                P_hat[0]['order_request_time'], "%d-%m-%Y %H:%M:%S") < self.t_Pmax:  # if postponement set is empty
                return True
            else:
                return False
        except Exception as e:
            logging.critical(e, exc_info=True)

    def updateDriver(self, driverList):
        try:
            for driver in list(filter(lambda driver: len(driver['Route']) > 0, driverList)):
                driver['Velocity'] = self.velocity
                self.DBclient.updateDriver(driver)
        except Exception as e:
            logging.critical(e, exc_info=True)

    def updatePosponedOrder(self, pospondList):

        for order in pospondList:
            try:
                order['order_status'] = 'waiting'
                self.DBclient.updateOrder(order)
            except Exception as e:
                logging.critical(e, exc_info=True)

    def updatePairdOrder(self, pairedOrderList):
        try:
            for order in pairedOrderList:
                order['order_status'] = 'headToRes'
                order['order_approved_at'] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
                order['order_estimated_delivery_date'] = (datetime.now() + self.deadlineTime).strftime(
                    "%d-%m-%Y %H:%M:%S")
                self.DBclient.updateOrder(order)
        except Exception as e:
            logging.critical(e, exc_info=True)

    def Qing(self, Ds_0, restaurant, drlist, city, q_setting):
        # for episode in range(self.total_episodes):

        # for order in Ds_0:
        try:
            rest_pos = [float(restaurant['Latitude']), float(restaurant['Longitude'])]
            delivery_pos = [float(Ds_0['Latitude']), float(Ds_0['Longitude'])]
            agents_dis = np.zeros((5, 1))  # 存距離
            agents_delay = np.zeros((5, 1))  # 存delay
            agents = []  # vehicle class
            counter = 0
            low_capacity = 5
            testlist = []
            for v in drlist:
                v_delay = self.deltaSDelay(v['Route'], v['Longitude'], v['Latitude'])
                v_capacity = int(v['Capacity'])
                if low_capacity > 5:
                    print(low_capacity)
                if v_capacity > low_capacity:
                    continue
                elif v_capacity < low_capacity:
                    low_capacity = v_capacity
                    agents = []
                    counter = 0
                    agents_dis = np.zeros((5, 1))  # nearBY
                    agents_delay = np.zeros((5, 1))
                vehicle_pos = [float(v['Latitude']), float(v['Longitude'])]
                dist = Geometry.coorDistance(vehicle_pos[0], vehicle_pos[1], rest_pos[0], rest_pos[1])
                if counter < 5:
                    agents_dis[counter] = dist
                    agents_delay[counter] = v_delay
                    agents.append(v)
                    counter += 1
                else:
                    index = np.argmax(agents_delay)
                    if agents_delay[index] > v_delay:
                        agents_delay[index] = v_delay
                        agents_dis[index] = dist
                        agents[index] = v
                    elif agents_delay[index] == v_delay:
                        if agents_dis[index] > dist:
                            agents_delay[index] = v_delay
                            agents_dis[index] = dist
                            agents[index] = v
            action = 0
            agent = 0
            for agent in agents:
                agent_pos = [agent['Latitude'], agent['Longitude']]

                state = [int(abs(float(city['Latitude']) - city['radius'] - agent_pos[0]) / (city['radius'] * 2 / 50)),
                         int(abs(float(city['Longitude']) - city['radius'] - agent_pos[1]) / (city['radius'] * 2 / 50))]
                state = state[0] * 50 + state[1]
                # decide action
                exp_exp_tradeoff = random.uniform(0, 1)
                # q_setting = self.DBclient.getQlearning(city)
                index = 0
                if exp_exp_tradeoff > q_setting['epsilon']:

                    # action = np.argmax(q_setting['q_table'][state, :])#Change
                    if q_setting['q_table'][state][0] > q_setting['q_table'][state][1]:
                        action = 0
                    elif q_setting['q_table'][state][0] < q_setting['q_table'][state][1]:
                        action = 1
                    else:
                        s = random.randint(0, 1)
                        if s == 0:
                            action = 0
                        else:
                            action = 1
                else:
                    action = random.randint(0, 1)
                if action == 1:
                    break
            # if all agent false take order
            '''if agents == []:
                print(low_capacity)
                print(counter)
                print(agents)'''
            if action == 0:
                # print(len(agents))
                agent = agents[0]
                state = [int(abs(float(city['Latitude']) - city['radius'] - agent_pos[0]) / (city['radius'] * 2 / 50)),
                         int(abs(float(city['Longitude']) - city['radius'] - agent_pos[1]) / (city['radius'] * 2 / 50))]
                state = state[0] * 50 + state[1]
                action = 1

            # check if agent has order not finish yet
            # self.driver_old_status = [] #len(drivierlist),[driverId,state,reward]
            agent_capacity = low_capacity
            agent_id = agent['Driver_ID']
            old_state = 0
            old_reward = 0
            old_state = 0
            order_id = 0
            agent_index = 0
            if agent_capacity > 0:
                for i in range(0, len(drlist)):
                    if drlist[i]['Driver_ID'] == agent_id:
                        agent_index = i
                        old_state = drlist[i]['State']
                        old_reward = drlist[i]['Reward']
                        q_setting['q_table'][old_state][1] = old_reward  # state write back to qtable
                        # q_setting['q_table'][old_state,1] = old_reward  # state write back to qtable
                        drlist[i]['State'] = state  # get new state status
                        drlist[i]['Reward'] = q_setting['q_table'][state][1]  # current state old reward
                        break

            # Take the action with environment
            # self.agent_orders_state = [] #len(driverList),np.array((5,2)) [driverid,np(5,2)],np(5,2)->[orderid,state]
            '''
            for i in range(0, len(drlist)):
                if drlist[i]['Driver_ID'] == agent_id:
                    agent_order_list = drlist[i]['order_list']  # get numpy array
                    for k in range(0, len(agent_order_list)):
                        if drlist[i]['order_list'][k][0] == 0:
                            drlist[i]['order_list'][k][0] = Ds_0['Order_ID']
                            drlist[i]['order_list'][k][1] = state
                            break
            '''
            Ds_0['Qtable_position'] = state

            # new_state = [float(Ds_0['Latitude']),float(Ds_0['Longitude'])]
            new_state = [
                int(abs(float(city['Latitude']) - city['radius'] - delivery_pos[0]) / (city['radius'] * 2 / 50)),
                int(abs(float(city['Longitude']) - city['radius'] - delivery_pos[1]) / (city['radius'] * 2 / 50))]
            new_state = new_state[0] * 50 + new_state[1]
            reward = Geometry.coorDistance(rest_pos[0], rest_pos[1], delivery_pos[0], delivery_pos[1]) / (
                        (Geometry.coorDistance(rest_pos[0],
                                               rest_pos[1], delivery_pos[0], delivery_pos[
                                                   1]) * 111 / self.velocity) * 60 + 20)  # (resturant to delivery distance)/(finish time)

            # update q_table
            # print(new_state)
            action_0 = q_setting['q_table'][new_state][0]
            action_1 = q_setting['q_table'][new_state][1]
            max = 0
            if action_0 > action_1:
                max = action_0
            elif action_0 < action_1:
                max = action_1
            else:
                s = random.randint(0, 1)
                if s == 0:
                    max = action_0
                else:
                    max = action_1
            # print(action)
            q_setting['q_table'][state][action] = q_setting['q_table'][state][action] + q_setting['learning_rate'] * (
                    reward + q_setting['gamma'] * max - q_setting['q_table'][state][action])

            return_index = next((index for (index, d) in enumerate(drlist) if d['Driver_ID'] == agent_id), None)

            # reward = resturant&delivery distance / finish time

            q_setting['episode'] += 1
            # reduce episode
            q_setting['epsilon'] = q_setting['min_epislon'] + (
                        q_setting['max_epislon'] - q_setting['min_epislon']) * np.exp(
                -q_setting['decay_rate'] * q_setting['episode'])
            self.DBclient.updateQlearning(q_setting)
            return return_index
        except Exception as e:
            logging.critical(e, exc_info=True)

    def real_reward(self, order, reward, q_setting):
        try:
            '''
            v_index = next((index for (index, d) in enumerate(vehicle_List) if d['Driver_ID'] == agent_id), None)
            for k in range(0, 5):
                if order_id == vehicle_List[v_index]['order_list'][k][0]:
                    state = vehicle_List[v_index]['order_list'][k][1]
                    q_setting['q_table'][state][1] = reward
                    vehicle_List[v_index]['order_list'][k][0] = 0
                    vehicle_List[v_index]['order_list'][k][1] = 0
                    break
            self.DBclient.updateDriver(vehicle_List[v_index])
            '''
            q_setting['q_table'][order['Qtable_position']][1] = reward
            order['Qtable_updated'] = 1
            self.DBclient.updateOrder(order)
            self.DBclient.updateQlearning(q_setting)
        except Exception as e:
            logging.critical(e, exc_info=True)

        '''
        for i in len(vehicle_List):
            if agent_id == vehicle_List[i]['Driver_ID']:
                agent_order = vehicle_List[i]['order_list']
                for k in range(0,len(agent_order)):
                    if order_id == vehicle_List[i]['order_list'][k][0]:
                        state = vehicle_List[i]['order_list'][k][1]
                        q_setting['q_table'][state][1] = reward
                        vehicle_List[i]['order_list'][k][0] = 0
                        vehicle_List[i]['order_list'][k][1] = 0
                        self.DBclient.updateDriver(vehicle_List[i])
                        self.DBclient.updateQlearning(q_setting)
        '''


TEST = RMDP()
TEST.generateThread()
